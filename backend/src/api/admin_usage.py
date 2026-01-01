from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..domain import UsageResponse, UsageBucket, UsageTopUser
from ..repositories import UsageAggregateRepository
from .deps import require_admin

router = APIRouter(prefix="/admin/usage", tags=["usage"], dependencies=[Depends(require_admin)])


@router.get("", response_model=UsageResponse)
async def get_usage(
    user_id: UUID | None = None,
    access_key_id: UUID | None = None,
    bucket_type: str = Query(default="hour", pattern="^(minute|hour|day|week|month)$"),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    session: AsyncSession = Depends(get_session),
):
    repo = UsageAggregateRepository(session)

    # Default time range: last 24 hours
    if not end_time:
        end_time = datetime.utcnow()
    if not start_time:
        start_time = end_time - timedelta(hours=24)

    aggregates = await repo.query_bucket_totals(
        bucket_type=bucket_type,
        start_time=start_time,
        end_time=end_time,
        user_id=user_id,
        access_key_id=access_key_id,
    )

    totals = await repo.get_totals(
        bucket_type=bucket_type,
        start_time=start_time,
        end_time=end_time,
        user_id=user_id,
        access_key_id=access_key_id,
    )

    buckets = [
        UsageBucket(
            bucket_start=a["bucket_start"],
            requests=a["total_requests"],
            input_tokens=a["total_input_tokens"],
            output_tokens=a["total_output_tokens"],
            total_tokens=a["total_tokens"],
        )
        for a in aggregates
    ]

    return UsageResponse(
        buckets=buckets,
        total_requests=totals["total_requests"],
        total_input_tokens=totals["total_input_tokens"],
        total_output_tokens=totals["total_output_tokens"],
        total_tokens=totals["total_tokens"],
    )


@router.get("/top-users", response_model=list[UsageTopUser])
async def get_top_users(
    bucket_type: str = Query(default="hour", pattern="^(minute|hour|day|week|month)$"),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
):
    repo = UsageAggregateRepository(session)

    if not end_time:
        end_time = datetime.utcnow()
    if not start_time:
        start_time = end_time - timedelta(hours=24)

    results = await repo.get_top_users(
        bucket_type=bucket_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

    return [
        UsageTopUser(
            user_id=row["user_id"],
            name=row["name"],
            total_tokens=row["total_tokens"],
            total_requests=row["total_requests"],
        )
        for row in results
    ]
