from dataclasses import dataclass

from ..domain import AnthropicRequest, AnthropicResponse, AnthropicUsage, RETRYABLE_ERRORS, ErrorType
from ..logging import get_logger
from .context import RequestContext
from .adapter_base import AdapterResponse, AdapterError, Adapter
from .dependencies import get_proxy_deps

logger = get_logger(__name__)

# Map internal error types to Anthropic API error types
ANTHROPIC_ERROR_TYPE_MAP = {
    ErrorType.RATE_LIMIT:             "rate_limit_error",
    ErrorType.USAGE_LIMIT:            "rate_limit_error",
    ErrorType.SERVER_ERROR:           "api_error",
    ErrorType.CLIENT_ERROR:           "invalid_request_error",
    ErrorType.TIMEOUT:                "overloaded_error",
    ErrorType.NETWORK_ERROR:          "api_error",
    ErrorType.BEDROCK_AUTH_ERROR:     "authentication_error",
    ErrorType.BEDROCK_QUOTA_EXCEEDED: "rate_limit_error",
    ErrorType.BEDROCK_VALIDATION:     "invalid_request_error",
    ErrorType.BEDROCK_MODEL_ERROR:    "api_error",
    ErrorType.BEDROCK_UNAVAILABLE:    "overloaded_error",
}


def _map_error_type(error_type: ErrorType) -> str:
    return ANTHROPIC_ERROR_TYPE_MAP.get(error_type, "api_error")


@dataclass
class ProxyResponse:
    """Final proxy response."""

    success: bool
    response: AnthropicResponse | None
    usage: AnthropicUsage | None
    provider: str  # "plan" or "bedrock"
    is_fallback: bool
    status_code: int
    error_type: str | None = None
    error_message: str | None = None


class ProxyRouter:
    """Routes requests between Plan and Bedrock."""

    def __init__(self, plan_adapter: Adapter, bedrock_adapter: Adapter):
        self._plan = plan_adapter
        self._bedrock = bedrock_adapter

    async def route(
        self, ctx: RequestContext, request: AnthropicRequest
    ) -> ProxyResponse:
        key_id = str(ctx.access_key_id)
        cb = get_proxy_deps().circuit_breaker
        plan_attempted = False

        if not cb.is_open(key_id):
            plan_attempted = True
            result = await self._plan.invoke(ctx, request)

            if isinstance(result, AdapterResponse):
                cb.record_success(key_id)
                return self._success_response("plan", result, is_fallback=False)

            cb.record_failure(key_id, result.error_type)

            should_fallback = result.retryable and result.error_type in RETRYABLE_ERRORS
            if not should_fallback:
                return self._error_response("plan", result, is_fallback=False)
        else:
            logger.info("plan_skipped_circuit_open", access_key_id=key_id)

        if ctx.has_bedrock_key:
            result = await self._bedrock.invoke(ctx, request)

            if isinstance(result, AdapterResponse):
                return self._success_response("bedrock", result, is_fallback=plan_attempted)

            return self._error_response("bedrock", result, is_fallback=plan_attempted)

        return ProxyResponse(
            success=False,
            response=None,
            usage=None,
            provider="plan",
            is_fallback=False,
            status_code=503,
            error_type="overloaded_error",
            error_message="Service unavailable and no fallback configured",
        )

    def _success_response(
        self, provider: str, result: AdapterResponse, is_fallback: bool
    ) -> ProxyResponse:
        return ProxyResponse(
            success=True,
            response=result.response,
            usage=result.usage,
            provider=provider,
            is_fallback=is_fallback,
            status_code=200,
        )

    def _error_response(
        self, provider: str, error: AdapterError, is_fallback: bool
    ) -> ProxyResponse:
        return ProxyResponse(
            success=False,
            response=None,
            usage=None,
            provider=provider,
            is_fallback=is_fallback,
            status_code=error.status_code,
            error_type=_map_error_type(error.error_type),
            error_message=error.message,
        )
