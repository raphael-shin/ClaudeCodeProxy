import time
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
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

    # Extract and pass through auth headers as-is
    x_api_key = raw_request.headers.get("x-api-key")
    authorization = raw_request.headers.get("authorization")
    outgoing_headers: dict[str, str] = {}
    if x_api_key:
        outgoing_headers["x-api-key"] = x_api_key
    if authorization:
        outgoing_headers["Authorization"] = authorization
    for header_name in ("anthropic-version", "anthropic-beta", "content-type"):
        header_value = raw_request.headers.get(header_name)
        if header_value:
            outgoing_headers[header_name] = header_value

    # Log header presence to confirm how Claude Code sends tokens (do not log secrets)
    logger.info(
        "proxy_auth_headers",
        has_x_api_key=bool(x_api_key),
        has_authorization=bool(authorization),
        authorization_is_bearer=bool(authorization and authorization.startswith("Bearer ")),
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
    usage_recorder = UsageRecorder(token_usage_repo, usage_aggregate_repo)

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

    # Extract and pass through auth headers as-is
    x_api_key = raw_request.headers.get("x-api-key")
    authorization = raw_request.headers.get("authorization")
    outgoing_headers: dict[str, str] = {}
    if x_api_key:
        outgoing_headers["x-api-key"] = x_api_key
    if authorization:
        outgoing_headers["Authorization"] = authorization
    for header_name in ("anthropic-version", "anthropic-beta", "content-type"):
        header_value = raw_request.headers.get(header_name)
        if header_value:
            outgoing_headers[header_name] = header_value

    settings = get_settings()
    if not x_api_key and not authorization and not settings.plan_api_key:
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
