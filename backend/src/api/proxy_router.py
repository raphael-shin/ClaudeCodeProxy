import time
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session, async_session_factory
from ..config import get_settings
from ..domain import AnthropicRequest, AnthropicError, AnthropicCountTokensResponse, RETRYABLE_ERRORS
from ..logging import get_logger
from ..repositories import BedrockKeyRepository, TokenUsageRepository, UsageAggregateRepository
from ..proxy import (
    AuthService,
    get_auth_service,
    ProxyRouter,
    PlanAdapter,
    BedrockAdapter,
    UsageRecorder,
)
from ..proxy.adapter_base import AdapterError
from ..proxy.router import _map_error_type

logger = get_logger(__name__)

router = APIRouter()

_PASSTHROUGH_HEADERS = ("anthropic-version", "anthropic-beta", "content-type")


def _extract_outgoing_headers(raw_request: Request) -> dict[str, str]:
    """Extract auth and passthrough headers from incoming request."""
    headers: dict[str, str] = {}
    if x_api_key := raw_request.headers.get("x-api-key"):
        headers["x-api-key"] = x_api_key
    if authorization := raw_request.headers.get("authorization"):
        headers["Authorization"] = authorization
    for name in _PASSTHROUGH_HEADERS:
        if value := raw_request.headers.get(name):
            headers[name] = value
    return headers


@router.post("/ak/{access_key}/v1/messages")
async def proxy_messages(
    access_key: str,
    request: AnthropicRequest,
    raw_request: Request,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
):
    start_time = time.time()

    # Authenticate
    ctx = await auth_service.authenticate(access_key)
    if not ctx:
        raise HTTPException(status_code=404, detail="Not found")

    outgoing_headers = _extract_outgoing_headers(raw_request)

    # Log header presence (do not log secrets)
    logger.info(
        "proxy_auth_headers",
        has_x_api_key="x-api-key" in outgoing_headers,
        has_authorization="Authorization" in outgoing_headers,
        authorization_is_bearer=outgoing_headers.get("Authorization", "").startswith("Bearer "),
    )

    if request.stream:
        plan_adapter = PlanAdapter(headers=outgoing_headers)
        bedrock_adapter = None
        streaming_started = False
        try:
            result = await plan_adapter.stream(request)
            if isinstance(result, AdapterError):
                if ctx.has_bedrock_key and result.retryable and result.error_type in RETRYABLE_ERRORS:
                    bedrock_adapter = BedrockAdapter(BedrockKeyRepository(session))
                    bedrock_result = await bedrock_adapter.stream(ctx, request)
                    if isinstance(bedrock_result, AdapterError):
                        error_body = AnthropicError(
                            error={"type": _map_error_type(bedrock_result.error_type), "message": bedrock_result.message},
                            request_id=ctx.request_id,
                        ).model_dump()
                        return JSONResponse(content=error_body, status_code=bedrock_result.status_code)

                    streaming_started = True

                    async def bedrock_stream_generator():
                        try:
                            async for chunk in bedrock_result:
                                yield chunk
                        finally:
                            await bedrock_adapter.close()

                    return StreamingResponse(
                        bedrock_stream_generator(),
                        media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
                    )

                error_body = AnthropicError(
                    error={"type": _map_error_type(result.error_type), "message": result.message},
                    request_id=ctx.request_id,
                ).model_dump()
                return JSONResponse(content=error_body, status_code=result.status_code)

            streaming_started = True

            async def stream_generator():
                try:
                    async for chunk in result.aiter_bytes():
                        yield chunk
                finally:
                    await result.aclose()
                    await plan_adapter.close()

            media_type = result.headers.get("content-type", "text/event-stream")
            return StreamingResponse(
                stream_generator(),
                media_type=media_type,
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
        finally:
            if not streaming_started:
                await plan_adapter.close()
                if bedrock_adapter:
                    await bedrock_adapter.close()

    # Setup adapters
    token_usage_repo = TokenUsageRepository(session)
    usage_aggregate_repo = UsageAggregateRepository(session)

    plan_adapter = PlanAdapter(headers=outgoing_headers)
    bedrock_adapter = BedrockAdapter(BedrockKeyRepository(session))
    proxy_router = ProxyRouter(plan_adapter, bedrock_adapter)
    usage_recorder = UsageRecorder(
        token_usage_repo,
        usage_aggregate_repo,
        session_factory=async_session_factory,
    )

    try:
        # Route request
        response = await proxy_router.route(ctx, request)

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Record usage
        await usage_recorder.record(ctx, response, latency_ms, request.model)
        await session.commit()

        if response.success and response.response:
            return response.response.model_dump()

        # Return error with proper HTTP status code
        error_body = AnthropicError(
            error={"type": response.error_type, "message": response.error_message},
            request_id=ctx.request_id,
        ).model_dump()
        return JSONResponse(content=error_body, status_code=response.status_code)

    finally:
        await plan_adapter.close()
        await bedrock_adapter.close()


@router.post("/ak/{access_key}/v1/messages/count_tokens")
async def proxy_count_tokens(
    access_key: str,
    request: AnthropicRequest,
    raw_request: Request,
    auth_service: AuthService = Depends(get_auth_service),
):
    # Authenticate
    ctx = await auth_service.authenticate(access_key)
    if not ctx:
        raise HTTPException(status_code=404, detail="Not found")

    outgoing_headers = _extract_outgoing_headers(raw_request)

    settings = get_settings()
    if "x-api-key" not in outgoing_headers and "Authorization" not in outgoing_headers and not settings.plan_api_key:
        error_body = AnthropicError(
            error={
                "type": "authentication_error",
                "message": "Missing API key for count_tokens",
            },
            request_id=ctx.request_id,
        ).model_dump()
        return JSONResponse(content=error_body, status_code=401)

    plan_adapter = PlanAdapter(headers=outgoing_headers)
    try:
        result = await plan_adapter.count_tokens(request)
        if isinstance(result, AnthropicCountTokensResponse):
            return result.model_dump()

        error_body = AnthropicError(
            error={"type": _map_error_type(result.error_type), "message": result.message},
            request_id=ctx.request_id,
        ).model_dump()
        return JSONResponse(content=error_body, status_code=result.status_code)
    finally:
        await plan_adapter.close()


@router.get("/health")
async def health():
    return {"status": "healthy"}
