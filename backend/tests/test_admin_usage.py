from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4
import sys
from pathlib import Path

import pytest

root = Path(__file__).resolve().parents[1]
sys.path.append(str(root))

from src.api import admin_usage
from src.domain import UsageResponse


class FakeUsageAggregateRepository:
    def __init__(self, _session) -> None:
        return None

    async def query_bucket_totals(self, **_kwargs):
        return [
            {
                "bucket_start": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "total_requests": 2,
                "total_input_tokens": 100,
                "total_output_tokens": 50,
                "total_tokens": 150,
                "total_cache_write_tokens": 5,
                "total_cache_read_tokens": 3,
                "total_input_cost_usd": Decimal("0.100000"),
                "total_output_cost_usd": Decimal("0.050000"),
                "total_cache_write_cost_usd": Decimal("0.010000"),
                "total_cache_read_cost_usd": Decimal("0.005000"),
                "total_estimated_cost_usd": Decimal("0.165000"),
            }
        ]

    async def get_totals(self, **_kwargs):
        return {
            "total_requests": 2,
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "total_tokens": 150,
            "total_cache_write_tokens": 5,
            "total_cache_read_tokens": 3,
            "total_input_cost_usd": Decimal("0.100000"),
            "total_output_cost_usd": Decimal("0.050000"),
            "total_cache_write_cost_usd": Decimal("0.010000"),
            "total_cache_read_cost_usd": Decimal("0.005000"),
            "total_estimated_cost_usd": Decimal("0.165000"),
        }


class FakeTokenUsageRepository:
    def __init__(self, _session) -> None:
        return None

    async def get_cost_breakdown_by_model(self, **_kwargs):
        return [
            {
                "pricing_model_id": "claude-opus-4-5",
                "input_cost_usd": Decimal("0.100000"),
                "output_cost_usd": Decimal("0.050000"),
                "cache_write_cost_usd": Decimal("0.010000"),
                "cache_read_cost_usd": Decimal("0.005000"),
                "total_cost_usd": Decimal("0.165000"),
            }
        ]


# Feature: cost-visibility, Property 5: Usage Summary API Response Completeness
@pytest.mark.asyncio
async def test_get_usage_response_includes_costs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_usage, "UsageAggregateRepository", FakeUsageAggregateRepository)
    monkeypatch.setattr(admin_usage, "TokenUsageRepository", FakeTokenUsageRepository)

    response = await admin_usage.get_usage(
        user_id=uuid4(),
        team_id=None,
        access_key_id=None,
        bucket_type="day",
        period=None,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 1),
        session=None,
    )

    assert isinstance(response, UsageResponse)
    assert response.total_cache_write_tokens == 5
    assert response.total_cache_read_tokens == 3
    assert response.total_input_cost_usd == "0.100000"
    assert response.total_output_cost_usd == "0.050000"
    assert response.estimated_cost_usd == "0.165000"
    assert response.cost_breakdown[0].model_id == "claude-opus-4-5"
    assert response.cost_breakdown[0].total_cost_usd == "0.165000"


# Feature: cost-visibility, Property 10: KST Bucket Boundaries

def test_resolve_time_range_week_starts_sunday_kst() -> None:
    now_utc = datetime(2025, 1, 6, 3, 0, tzinfo=timezone.utc)  # Monday noon KST

    start_utc, end_utc = admin_usage._resolve_time_range(
        period="week",
        start_date=None,
        end_date=None,
        now_utc=now_utc,
    )

    assert start_utc == datetime(2025, 1, 4, 15, 0, tzinfo=timezone.utc)
    assert end_utc == now_utc
