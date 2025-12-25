"""Usage recording to database."""
import asyncio
from datetime import datetime, timedelta

from ..logging import get_logger
from ..repositories import TokenUsageRepository, UsageAggregateRepository
from .context import RequestContext
from .router import ProxyResponse
from .metrics import CloudWatchMetricsEmitter

logger = get_logger(__name__)


def _get_bucket_start(ts: datetime, bucket_type: str) -> datetime:
    if bucket_type == "minute":
        return ts.replace(second=0, microsecond=0)
    elif bucket_type == "hour":
        return ts.replace(minute=0, second=0, microsecond=0)
    elif bucket_type == "day":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    elif bucket_type == "week":
        days_since_monday = ts.weekday()
        return (ts - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif bucket_type == "month":
        return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return ts.replace(minute=0, second=0, microsecond=0)


class UsageRecorder:
    """Records usage to database and emits metrics."""

    def __init__(
        self,
        token_usage_repo: TokenUsageRepository,
        usage_aggregate_repo: UsageAggregateRepository,
        metrics_emitter: CloudWatchMetricsEmitter | None = None,
    ):
        self._repo = token_usage_repo
        self._agg_repo = usage_aggregate_repo
        self._metrics = metrics_emitter or CloudWatchMetricsEmitter()

    async def record(
        self,
        ctx: RequestContext,
        response: ProxyResponse,
        latency_ms: int,
        model: str,
    ) -> None:
        # Log to CloudWatch Logs (structured)
        logger.info(
            "request_completed",
            request_id=ctx.request_id,
            access_key_prefix=ctx.access_key_prefix,
            provider_used=response.provider,
            is_fallback=response.is_fallback,
            status_code=response.status_code,
            error_type=response.error_type,
            latency_ms=latency_ms,
            model=model,
        )

        # Emit metrics (fire and forget)
        asyncio.create_task(self._metrics.emit(response, latency_ms))

        # Record token usage to DB (Bedrock success only)
        if response.success and response.provider == "bedrock" and response.usage:
            now = datetime.utcnow()
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens

            await self._repo.create(
                request_id=ctx.request_id,
                user_id=ctx.user_id,
                access_key_id=ctx.access_key_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                is_fallback=response.is_fallback,
                latency_ms=latency_ms,
                cache_read_input_tokens=response.usage.cache_read_input_tokens,
                cache_creation_input_tokens=response.usage.cache_creation_input_tokens,
            )

            # Update usage aggregates for all bucket types
            for bucket_type in ("minute", "hour", "day", "week", "month"):
                bucket_start = _get_bucket_start(now, bucket_type)
                await self._agg_repo.increment(
                    bucket_type=bucket_type,
                    bucket_start=bucket_start,
                    user_id=ctx.user_id,
                    access_key_id=ctx.access_key_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                )
