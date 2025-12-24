import asyncio
from datetime import datetime, timedelta
from uuid import UUID

import boto3

from ..logging import get_logger
from ..config import get_settings
from ..repositories import TokenUsageRepository, UsageAggregateRepository
from .context import RequestContext
from .router import ProxyResponse

logger = get_logger(__name__)


def _get_bucket_start(ts: datetime, bucket_type: str) -> datetime:
    if bucket_type == "minute":
        return ts.replace(second=0, microsecond=0)
    elif bucket_type == "hour":
        return ts.replace(minute=0, second=0, microsecond=0)
    elif bucket_type == "day":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    elif bucket_type == "week":
        # Start of week (Monday)
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
    ):
        self._repo = token_usage_repo
        self._agg_repo = usage_aggregate_repo
        self._cw = boto3.client("cloudwatch", region_name=get_settings().bedrock_region)
        self._namespace = "ClaudeCodeProxy"

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
        asyncio.create_task(self._emit_metrics(response, latency_ms))

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

    async def _emit_metrics(self, response: ProxyResponse, latency_ms: int) -> None:
        try:
            metrics = [
                {
                    "MetricName": "RequestCount",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "Provider", "Value": response.provider}],
                },
                {
                    "MetricName": "RequestLatency",
                    "Value": latency_ms,
                    "Unit": "Milliseconds",
                    "Dimensions": [{"Name": "Provider", "Value": response.provider}],
                },
            ]

            if response.error_type:
                metrics.append({
                    "MetricName": "ErrorCount",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "ErrorType", "Value": response.error_type},
                        {"Name": "Provider", "Value": response.provider},
                    ],
                })

            if response.is_fallback:
                metrics.append({
                    "MetricName": "FallbackCount",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [],
                })

            if response.usage and response.provider == "bedrock":
                metrics.extend([
                    {
                        "MetricName": "BedrockTokensUsed",
                        "Value": response.usage.input_tokens,
                        "Unit": "Count",
                        "Dimensions": [{"Name": "TokenType", "Value": "input"}],
                    },
                    {
                        "MetricName": "BedrockTokensUsed",
                        "Value": response.usage.output_tokens,
                        "Unit": "Count",
                        "Dimensions": [{"Name": "TokenType", "Value": "output"}],
                    },
                ])

            self._cw.put_metric_data(Namespace=self._namespace, MetricData=metrics)
        except Exception as e:
            logger.warning("metrics_emission_failed", error=str(e))
