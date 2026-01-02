# Design Document: Cost Visibility

## Overview

이 설계 문서는 Claude 4.5 모델의 토큰 사용량 기반 비용 가시성 기능을 구현하기 위한 아키텍처와 컴포넌트를 정의한다. 기존 프록시 시스템의 사용량 추적 기능을 확장하여 모델별 단가 관리, 비용 계산, API 확장, 대시보드 통합을 제공한다. 모든 저장 시각은 UTC로 유지하되, 기간 필터와 버킷 경계는 Asia/Seoul(UTC+9) 기준으로 계산 후 UTC로 변환한다. 주간 경계는 KST 기준 일요일 시작이다.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Admin Dashboard                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Cost Summary│  │Model Chart  │  │ Cost Trend Graph        │ │
│  │    Card     │  │(Breakdown)  │  │ (Time Series)           │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Backend API                             │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │GET /admin/usage │  │GET /api/pricing │                      │
│  │  (extended)     │  │    /models      │                      │
│  └────────┬────────┘  └────────┬────────┘                      │
│           │                    │                                │
│           ▼                    ▼                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Cost Calculator                          ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  ││
│  │  │ Model Pricing│  │ Cost Formula │  │ Aggregation      │  ││
│  │  │   Config     │  │  Engine      │  │   Logic          │  ││
│  │  └──────────────┘  └──────────────┘  └──────────────────┘  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Layer                               │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │  token_usage    │  │ usage_aggregates│                      │
│  │ +cost snapshot  │  │ +cost +cache    │                      │
│  └─────────────────┘  └─────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Model Pricing Configuration

모델별, 리전별 단가 정보를 관리하는 설정 컴포넌트. 환경 변수 또는 설정 파일을 통해 런타임에 업데이트 가능하도록 설계한다.

```python
# backend/src/domain/pricing.py

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict
import json
import os

@dataclass(frozen=True)
class ModelPricing:
    """Pricing information for a single model."""
    model_id: str
    region: str
    input_price_per_million: Decimal
    output_price_per_million: Decimal
    cache_write_price_per_million: Decimal
    cache_read_price_per_million: Decimal
    effective_date: date

class PricingConfig:
    """Configuration for model pricing by region. Supports runtime updates."""
    
    # Default pricing by region (ap-northeast-2 as primary)
    _PRICING_DATA: Dict[str, Dict[str, ModelPricing]] = {}
    _initialized: bool = False
    
    @classmethod
    def _initialize(cls) -> None:
        """Initialize pricing from environment or defaults."""
        if cls._initialized:
            return
        
        # Try to load from environment variable (JSON string)
        pricing_json = os.environ.get("PROXY_MODEL_PRICING")
        if pricing_json:
            try:
                cls._load_from_json(pricing_json)
            except Exception:
                # Fallback to defaults on invalid config
                cls._load_defaults()
        else:
            cls._load_defaults()
        cls._initialized = True
    
    @classmethod
    def _load_defaults(cls) -> None:
        """Load default pricing (ap-northeast-2 region)."""
        default_region = "ap-northeast-2"
        effective_date = date(2025, 1, 1)
        
        cls._PRICING_DATA[default_region] = {
            "claude-opus-4-5": ModelPricing(
                model_id="claude-opus-4-5",
                region=default_region,
                input_price_per_million=Decimal("5.00"),
                output_price_per_million=Decimal("25.00"),
                cache_write_price_per_million=Decimal("6.25"),
                cache_read_price_per_million=Decimal("0.50"),
                effective_date=effective_date,
            ),
            "claude-sonnet-4-5": ModelPricing(
                model_id="claude-sonnet-4-5",
                region=default_region,
                input_price_per_million=Decimal("3.00"),
                output_price_per_million=Decimal("15.00"),
                cache_write_price_per_million=Decimal("3.75"),
                cache_read_price_per_million=Decimal("0.30"),
                effective_date=effective_date,
            ),
            "claude-haiku-4-5": ModelPricing(
                model_id="claude-haiku-4-5",
                region=default_region,
                input_price_per_million=Decimal("1.00"),
                output_price_per_million=Decimal("5.00"),
                cache_write_price_per_million=Decimal("1.25"),
                cache_read_price_per_million=Decimal("0.10"),
                effective_date=effective_date,
            ),
        }

    @classmethod
    def _load_from_json(cls, pricing_json: str) -> None:
        """Load pricing from JSON string in PROXY_MODEL_PRICING."""
        data = json.loads(pricing_json)
        for region, models in data.items():
            cls._PRICING_DATA[region] = {}
            for model_id, prices in models.items():
                cls._PRICING_DATA[region][model_id] = ModelPricing(
                    model_id=model_id,
                    region=region,
                    input_price_per_million=Decimal(str(prices["input_price_per_million"])),
                    output_price_per_million=Decimal(str(prices["output_price_per_million"])),
                    cache_write_price_per_million=Decimal(str(prices["cache_write_price_per_million"])),
                    cache_read_price_per_million=Decimal(str(prices["cache_read_price_per_million"])),
                    effective_date=date.fromisoformat(str(prices.get("effective_date", "1970-01-01"))),
                )
    
    @classmethod
    def reload(cls) -> None:
        """Force reload pricing configuration."""
        cls._initialized = False
        cls._PRICING_DATA.clear()
        cls._initialize()
    
    @classmethod
    def get_pricing(cls, model_id: str, region: str = "ap-northeast-2") -> ModelPricing | None:
        """Get pricing for a model in a specific region."""
        cls._initialize()
        normalized_id = cls._normalize_model_id(model_id)
        region_pricing = cls._PRICING_DATA.get(region, cls._PRICING_DATA.get("ap-northeast-2", {}))
        return region_pricing.get(normalized_id)
    
    @classmethod
    def get_all_pricing(cls, region: str = "ap-northeast-2") -> list[ModelPricing]:
        """Get pricing for all configured models in a region."""
        cls._initialize()
        region_pricing = cls._PRICING_DATA.get(region, cls._PRICING_DATA.get("ap-northeast-2", {}))
        return list(region_pricing.values())

    @classmethod
    def normalize_model_id(cls, model_id: str) -> str:
        """Public helper for normalized pricing keys."""
        return cls._normalize_model_id(model_id)
    
    @staticmethod
    def _normalize_model_id(model_id: str) -> str:
        """Normalize Bedrock model ID to pricing key."""
        # Known Bedrock model ID patterns
        MODEL_MAPPINGS = {
            "anthropic.claude-opus-4-5": "claude-opus-4-5",
            "anthropic.claude-sonnet-4-5": "claude-sonnet-4-5",
            "anthropic.claude-haiku-4-5": "claude-haiku-4-5",
            "global.anthropic.claude-opus-4-5": "claude-opus-4-5",
            "global.anthropic.claude-sonnet-4-5": "claude-sonnet-4-5",
            "global.anthropic.claude-haiku-4-5": "claude-haiku-4-5",
        }
        
        # Try exact prefix match first
        model_lower = model_id.lower()
        for prefix, normalized in MODEL_MAPPINGS.items():
            if model_lower.startswith(prefix):
                return normalized
        
        # Fallback: check for model family keywords
        if "opus" in model_lower and "4-5" in model_lower.replace("4.5", "4-5"):
            return "claude-opus-4-5"
        elif "sonnet" in model_lower and "4-5" in model_lower.replace("4.5", "4-5"):
            return "claude-sonnet-4-5"
        elif "haiku" in model_lower and "4-5" in model_lower.replace("4.5", "4-5"):
            return "claude-haiku-4-5"
        
        return model_id  # Return as-is if no match
```

`PROXY_MODEL_PRICING` JSON format example:

```json
{
  "ap-northeast-2": {
    "claude-opus-4-5": {
      "input_price_per_million": "5.00",
      "output_price_per_million": "25.00",
      "cache_write_price_per_million": "6.25",
      "cache_read_price_per_million": "0.50",
      "effective_date": "2025-01-01"
    }
  }
}
```

운영 중 가격 변경은 설정 업데이트 후 `PricingConfig.reload()`를 호출하는 관리용 엔드포인트(`/api/pricing/reload`)로 반영한다.

### 2. Cost Calculator

토큰 사용량과 단가를 기반으로 비용을 계산하는 컴포넌트. 토큰 타입별 비용을 개별적으로 계산하고 저장한다.

```python
# backend/src/domain/cost_calculator.py

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass

@dataclass
class CostBreakdown:
    """Detailed cost breakdown by token type."""
    input_cost: Decimal
    output_cost: Decimal
    cache_write_cost: Decimal
    cache_read_cost: Decimal
    total_cost: Decimal
    
    def to_dict(self) -> dict:
        """Convert to dictionary with string values for JSON serialization."""
        return {
            "input_cost": str(self.input_cost),
            "output_cost": str(self.output_cost),
            "cache_write_cost": str(self.cache_write_cost),
            "cache_read_cost": str(self.cache_read_cost),
            "total_cost": str(self.total_cost),
        }

class CostCalculator:
    """Calculates estimated costs based on token usage and model pricing."""
    
    PRECISION = Decimal("0.000001")  # 6 decimal places
    TOKENS_PER_MILLION = Decimal("1000000")
    
    @classmethod
    def calculate_cost(
        cls,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int,
        cache_read_tokens: int,
        pricing: ModelPricing,
    ) -> CostBreakdown:
        """Calculate cost breakdown for given token usage."""
        input_cost = cls._calculate_token_cost(
            input_tokens, pricing.input_price_per_million
        )
        output_cost = cls._calculate_token_cost(
            output_tokens, pricing.output_price_per_million
        )
        cache_write_cost = cls._calculate_token_cost(
            cache_write_tokens, pricing.cache_write_price_per_million
        )
        cache_read_cost = cls._calculate_token_cost(
            cache_read_tokens, pricing.cache_read_price_per_million
        )
        
        total_cost = (input_cost + output_cost + cache_write_cost + cache_read_cost).quantize(
            cls.PRECISION, rounding=ROUND_HALF_UP
        )
        
        return CostBreakdown(
            input_cost=input_cost,
            output_cost=output_cost,
            cache_write_cost=cache_write_cost,
            cache_read_cost=cache_read_cost,
            total_cost=total_cost,
        )
    
    @classmethod
    def _calculate_token_cost(cls, tokens: int, price_per_million: Decimal) -> Decimal:
        """Calculate cost for a specific token type."""
        if tokens <= 0:
            return Decimal("0.000000")
        cost = (Decimal(tokens) / cls.TOKENS_PER_MILLION) * price_per_million
        return cost.quantize(cls.PRECISION, rounding=ROUND_HALF_UP)
```

### 3. Extended Usage Recording (Background Task)

기존 UsageRecorder를 확장하여 비용 정보를 비동기적으로 저장한다. 응답 전송 후 백그라운드에서 비용 계산과 Pricing_Snapshot 저장을 수행하며, 버킷 경계는 KST 기준으로 계산한다.

```python
# Modifications to backend/src/proxy/usage.py

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

class UsageRecorder:
    """Records usage to database and emits metrics."""

    KST = ZoneInfo("Asia/Seoul")

    async def record(
        self,
        ctx: RequestContext,
        response: ProxyResponse,
        latency_ms: int,
        model: str,
    ) -> None:
        # Log immediately (non-blocking)
        logger.info(
            "request_completed",
            request_id=ctx.request_id,
            access_key_prefix=ctx.access_key_prefix,
            provider_used=response.provider,
            is_fallback=response.is_fallback,
            status_code=response.status_code,
            latency_ms=latency_ms,
            model=model,
        )

        # Emit metrics (fire and forget)
        asyncio.create_task(self._metrics.emit(response, latency_ms))

        # Record usage with cost in background (fire and forget)
        if response.success and response.provider == "bedrock" and response.usage:
            asyncio.create_task(
                self._record_usage_with_cost(ctx, response, latency_ms, model)
            )

    async def _record_usage_with_cost(
        self,
        ctx: RequestContext,
        response: ProxyResponse,
        latency_ms: int,
        model: str,
    ) -> None:
        """Background task to record usage with cost calculation."""
        try:
            now_utc = datetime.now(timezone.utc)
            now_kst = now_utc.astimezone(self.KST)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cache_write_tokens = response.usage.cache_creation_input_tokens or 0
            cache_read_tokens = response.usage.cache_read_input_tokens or 0
            total_tokens = input_tokens + output_tokens
            
            # Calculate costs
            cost_breakdown, pricing = self._calculate_cost_safe(
                model, ctx.bedrock_region, input_tokens, output_tokens,
                cache_write_tokens, cache_read_tokens
            )
            pricing_model_id = pricing.model_id if pricing else PricingConfig.normalize_model_id(model)
            
            # Store usage with cost breakdown
            await self._repo.create(
                request_id=ctx.request_id,
                user_id=ctx.user_id,
                access_key_id=ctx.access_key_id,
                model=model,
                pricing_model_id=pricing_model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                is_fallback=response.is_fallback,
                latency_ms=latency_ms,
                cache_read_input_tokens=cache_read_tokens,
                cache_creation_input_tokens=cache_write_tokens,
                estimated_cost_usd=cost_breakdown.total_cost,
                input_cost_usd=cost_breakdown.input_cost,
                output_cost_usd=cost_breakdown.output_cost,
                cache_write_cost_usd=cost_breakdown.cache_write_cost,
                cache_read_cost_usd=cost_breakdown.cache_read_cost,
                pricing_region=pricing.region if pricing else ctx.bedrock_region,
                pricing_effective_date=pricing.effective_date if pricing else None,
                pricing_input_price_per_million=pricing.input_price_per_million if pricing else Decimal("0"),
                pricing_output_price_per_million=pricing.output_price_per_million if pricing else Decimal("0"),
                pricing_cache_write_price_per_million=pricing.cache_write_price_per_million if pricing else Decimal("0"),
                pricing_cache_read_price_per_million=pricing.cache_read_price_per_million if pricing else Decimal("0"),
            )
            
            # Update aggregates
            for bucket_type in ("minute", "hour", "day", "week", "month"):
                # Week buckets start on Sunday in KST.
                bucket_start_kst = _get_bucket_start(now_kst, bucket_type, tz=self.KST)
                bucket_start = bucket_start_kst.astimezone(timezone.utc)
                await self._agg_repo.increment(
                    bucket_type=bucket_type,
                    bucket_start=bucket_start,
                    user_id=ctx.user_id,
                    access_key_id=ctx.access_key_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cache_write_tokens=cache_write_tokens,
                    cache_read_tokens=cache_read_tokens,
                    total_estimated_cost_usd=cost_breakdown.total_cost,
                    total_input_cost_usd=cost_breakdown.input_cost,
                    total_output_cost_usd=cost_breakdown.output_cost,
                    total_cache_write_cost_usd=cost_breakdown.cache_write_cost,
                    total_cache_read_cost_usd=cost_breakdown.cache_read_cost,
                )
        except Exception as e:
            logger.error("usage_recording_failed", error=str(e), request_id=ctx.request_id)
    
    def _calculate_cost_safe(
        self, model: str, region: str,
        input_tokens: int, output_tokens: int,
        cache_write_tokens: int, cache_read_tokens: int,
    ) -> tuple[CostBreakdown, ModelPricing | None]:
        """Calculate cost with error handling. Returns breakdown and pricing snapshot."""
        try:
            pricing = PricingConfig.get_pricing(model, region)
            if pricing:
                return CostCalculator.calculate_cost(
                    input_tokens, output_tokens,
                    cache_write_tokens, cache_read_tokens, pricing
                ), pricing
        except Exception as e:
            logger.warning("cost_calculation_failed", error=str(e), model=model)
        
        # Return zero costs on failure
        return CostBreakdown(
            input_cost=Decimal("0"),
            output_cost=Decimal("0"),
            cache_write_cost=Decimal("0"),
            cache_read_cost=Decimal("0"),
            total_cost=Decimal("0"),
        ), None
```

백그라운드 작업은 초기에는 in-process `create_task`로 처리하되, 유실 방지가 필요하면 작업 큐(예: DB/Redis 기반)로 전환하고 종료 시 대기/재시도를 보장한다.

## Data Models

Pricing_Snapshot은 별도 테이블이 아닌 `token_usage`에 단가 스냅샷을 비정규화로 저장한다. 이를 통해 요금 변경 후에도 과거 비용을 재계산 없이 감사할 수 있다.

### Database Schema Changes

#### token_usage 테이블 확장

```sql
-- Migration: Add cost tracking fields to token_usage
ALTER TABLE token_usage 
ADD COLUMN estimated_cost_usd DECIMAL(12, 6) NOT NULL DEFAULT 0,
ADD COLUMN input_cost_usd DECIMAL(12, 6) NOT NULL DEFAULT 0,
ADD COLUMN output_cost_usd DECIMAL(12, 6) NOT NULL DEFAULT 0,
ADD COLUMN cache_write_cost_usd DECIMAL(12, 6) NOT NULL DEFAULT 0,
ADD COLUMN cache_read_cost_usd DECIMAL(12, 6) NOT NULL DEFAULT 0,
ADD COLUMN pricing_region VARCHAR(32) NOT NULL DEFAULT 'ap-northeast-2',
ADD COLUMN pricing_model_id VARCHAR(64) NOT NULL DEFAULT '',
ADD COLUMN pricing_effective_date DATE,
ADD COLUMN pricing_input_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
ADD COLUMN pricing_output_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
ADD COLUMN pricing_cache_write_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0,
ADD COLUMN pricing_cache_read_price_per_million DECIMAL(12, 6) NOT NULL DEFAULT 0;
```

`pricing_*` 필드는 요청 시점의 단가 스냅샷을 저장하며, `pricing_model_id`는 모델별 비용 집계를 위한 정규화된 키로 사용한다.

#### usage_aggregates 테이블 확장

```sql
-- Migration: Add cost and cache token tracking to usage_aggregates
ALTER TABLE usage_aggregates 
ADD COLUMN total_cache_write_tokens BIGINT NOT NULL DEFAULT 0,
ADD COLUMN total_cache_read_tokens BIGINT NOT NULL DEFAULT 0,
ADD COLUMN total_input_cost_usd DECIMAL(15, 6) NOT NULL DEFAULT 0,
ADD COLUMN total_output_cost_usd DECIMAL(15, 6) NOT NULL DEFAULT 0,
ADD COLUMN total_cache_write_cost_usd DECIMAL(15, 6) NOT NULL DEFAULT 0,
ADD COLUMN total_cache_read_cost_usd DECIMAL(15, 6) NOT NULL DEFAULT 0,
ADD COLUMN total_estimated_cost_usd DECIMAL(15, 6) NOT NULL DEFAULT 0;
```

### SQLAlchemy Model Updates

```python
# backend/src/db/models.py

from datetime import date
from sqlalchemy import BigInteger, Date, Numeric, String

class TokenUsageModel(Base):
    __tablename__ = "token_usage"
    
    # ... existing fields ...
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    input_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    output_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    cache_write_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    cache_read_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    pricing_region: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ap-northeast-2"
    )
    pricing_model_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default=""
    )
    pricing_effective_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    pricing_input_price_per_million: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    pricing_output_price_per_million: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    pricing_cache_write_price_per_million: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    pricing_cache_read_price_per_million: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )

class UsageAggregateModel(Base):
    __tablename__ = "usage_aggregates"
    
    # ... existing fields ...
    total_cache_write_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    total_cache_read_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    total_input_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False, default=Decimal("0")
    )
    total_output_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False, default=Decimal("0")
    )
    total_cache_write_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False, default=Decimal("0")
    )
    total_cache_read_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False, default=Decimal("0")
    )
    total_estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False, default=Decimal("0")
    )
```

### API Response Schemas

```python
# backend/src/domain/schemas.py

from decimal import Decimal

class ModelPricingResponse(BaseModel):
    model_id: str
    region: str
    input_price: str  # String to preserve precision
    output_price: str
    cache_write_price: str
    cache_read_price: str
    effective_date: str

class PricingListResponse(BaseModel):
    models: list[ModelPricingResponse]
    region: str

class CostBreakdownByModel(BaseModel):
    model_id: str  # pricing_model_id (normalized)
    total_cost_usd: str
    input_cost_usd: str
    output_cost_usd: str
    cache_write_cost_usd: str
    cache_read_cost_usd: str

class UsageBucket(BaseModel):
    bucket_start: datetime  # UTC timestamp aligned to KST boundary
    requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cache_write_tokens: int  # NEW
    cache_read_tokens: int   # NEW
    input_cost_usd: str      # NEW
    output_cost_usd: str     # NEW
    cache_write_cost_usd: str  # NEW
    cache_read_cost_usd: str   # NEW
    estimated_cost_usd: str  # String for precision

class UsageResponse(BaseModel):
    buckets: list[UsageBucket]
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cache_write_tokens: int
    total_cache_read_tokens: int
    total_input_cost_usd: str
    total_output_cost_usd: str
    total_cache_write_cost_usd: str
    total_cache_read_cost_usd: str
    estimated_cost_usd: str  # String for precision
    cost_breakdown: list[CostBreakdownByModel]
```

### New API Endpoints

```python
# backend/src/api/admin_usage.py

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query
from ..domain.schemas import UsageResponse
from .deps import require_admin

router = APIRouter(prefix="/admin", tags=["usage"], dependencies=[Depends(require_admin)])
KST = ZoneInfo("Asia/Seoul")

@router.get("/usage", response_model=UsageResponse)
async def get_usage_summary(
    period: str | None = Query(default=None, description="day|week|month"),
    start_date: date | None = Query(default=None, description="YYYY-MM-DD (KST)"),
    end_date: date | None = Query(default=None, description="YYYY-MM-DD (KST)"),
    user_id: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
):
    """
    - period OR (start_date/end_date) 중 하나를 사용한다. 둘 다 있으면 date range 우선.
    - KST 기준으로 날짜 경계를 계산한 뒤 UTC로 변환해 조회한다.
    - 주간 경계는 KST 기준 일요일 시작.
    """
    if start_date and end_date:
        start_kst = datetime.combine(start_date, time.min, tzinfo=KST)
        end_kst = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=KST)
        start_utc = start_kst.astimezone(timezone.utc)
        end_utc = end_kst.astimezone(timezone.utc)
    elif period:
        # Compute KST-aligned window for day/week/month, then convert to UTC
        pass
    # ... query usage_aggregates/token_usage and return UsageResponse ...
```

`cost_breakdown`은 `pricing_model_id` 기준으로 `input_cost_usd`, `output_cost_usd`, `cache_write_cost_usd`, `cache_read_cost_usd`를 합산해 구성하며, 현재 단가로 재계산하지 않는다.
`team_id` 필터는 기존 사용자/팀 매핑 테이블을 조인하여 적용한다.

```python
# backend/src/api/admin_pricing.py

from fastapi import APIRouter, Depends, Query
from ..domain.pricing import PricingConfig
from ..domain.schemas import PricingListResponse, ModelPricingResponse
from .deps import require_admin

router = APIRouter(prefix="/api/pricing", tags=["pricing"], dependencies=[Depends(require_admin)])

@router.get("/models", response_model=PricingListResponse)
async def get_model_pricing(
    region: str = Query(default="ap-northeast-2"),
):
    """Get pricing information for all configured models."""
    pricing_list = PricingConfig.get_all_pricing(region)
    
    return PricingListResponse(
        region=region,
        models=[
            ModelPricingResponse(
                model_id=p.model_id,
                region=p.region,
                input_price=str(p.input_price_per_million),
                output_price=str(p.output_price_per_million),
                cache_write_price=str(p.cache_write_price_per_million),
                cache_read_price=str(p.cache_read_price_per_million),
                effective_date=p.effective_date.isoformat(),
            )
            for p in pricing_list
        ],
    )

@router.post("/reload", status_code=204)
async def reload_pricing() -> None:
    """Reload pricing config without restart."""
    PricingConfig.reload()
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Model Pricing Storage and Retrieval

*For any* valid model ID (claude-opus-4-5, claude-sonnet-4-5, claude-haiku-4-5) and supported region (ap-northeast-2), the PricingConfig SHALL return a ModelPricing object with all four price types (input, output, cache_write, cache_read) as positive Decimal values, along with region and effective_date.

**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Cost Calculation Formula Correctness

*For any* non-negative token count and positive price per million, the calculated cost SHALL equal `(tokens / 1,000,000) * price_per_million` rounded to 6 decimal places using ROUND_HALF_UP.

**Validates: Requirements 3.1, 3.4**

### Property 3: Cost Aggregation Correctness

*For any* combination of input_tokens, output_tokens, cache_write_tokens, and cache_read_tokens with valid pricing, the total_cost SHALL equal the sum of individual token type costs (input_cost + output_cost + cache_write_cost + cache_read_cost), each rounded to 6 decimal places.

**Validates: Requirements 3.2**

### Property 4: Token Usage Recording Completeness

*For any* request with usage data, the Token_Usage record SHALL contain:
- cache_creation_input_tokens matching the request's cache write tokens
- cache_read_input_tokens matching the request's cache read tokens  
- model matching the request's model ID
- estimated_cost_usd calculated from the token counts and model pricing
- Individual cost fields (input_cost_usd, output_cost_usd, cache_write_cost_usd, cache_read_cost_usd)
- pricing_region matching the request's region
- pricing_model_id and pricing_effective_date from Pricing_Snapshot
- pricing_*_price_per_million fields matching the snapshot used for calculation

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

### Property 5: Usage Summary API Response Completeness

*For any* time period with recorded usage, the Usage_Summary_API response SHALL include:
- total_cache_write_tokens equal to sum of all cache_creation_input_tokens in period
- total_cache_read_tokens equal to sum of all cache_read_input_tokens in period
- total_input_cost_usd, total_output_cost_usd, total_cache_write_cost_usd, total_cache_read_cost_usd equal to their respective sums
- estimated_cost_usd equal to sum of all stored estimated_cost_usd in period (no repricing)
- cost_breakdown (by pricing_model_id) with input/output/cache costs, where sum of all model costs equals estimated_cost_usd

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

### Property 6: Pricing API Response Completeness

*For any* call to GET /api/pricing/models with a valid region, the response SHALL contain:
- All configured models for that region
- Each entry with model_id, region, input_price, output_price, cache_write_price, cache_read_price, effective_date
- All prices as string representations preserving 6 decimal precision

**Validates: Requirements 5.1, 5.2, 5.3**

### Property 7: Model ID Normalization Consistency

*For any* Bedrock model ID string matching known patterns (e.g., "anthropic.claude-sonnet-4-5-*", "global.anthropic.claude-opus-4-5-*"), the normalization function SHALL consistently map it to the corresponding pricing key (claude-opus-4-5, claude-sonnet-4-5, or claude-haiku-4-5).

**Validates: Requirements 1.1, 3.3**

### Property 8: Error Resilience

*For any* request where cost calculation fails (e.g., unknown model, invalid pricing), the system SHALL:
- Log the error with context
- Continue processing the request without failure
- Store the usage record with all cost fields set to 0
- Not affect request latency

**Validates: Requirements 7.3**

### Property 9: Aggregate Cache Token Tracking

*For any* set of usage records in a time bucket, the usage_aggregates record SHALL have:
- total_cache_write_tokens equal to sum of cache_creation_input_tokens
- total_cache_read_tokens equal to sum of cache_read_input_tokens
- total_input_cost_usd, total_output_cost_usd, total_cache_write_cost_usd, total_cache_read_cost_usd equal to their respective sums
- total_estimated_cost_usd equal to sum of estimated_cost_usd

**Validates: Requirements 4.1, 4.2**

### Property 10: KST Bucket Boundaries

*For any* timestamp, bucket_start SHALL be computed using Asia/Seoul(UTC+9) boundaries and stored in UTC, ensuring day/week/month groupings align with KST dates.
Week boundaries start on Sunday in KST.

**Validates: Requirements 4.4**

## Error Handling

### Cost Calculation Errors

| Error Scenario | Handling Strategy |
|----------------|-------------------|
| Unknown model ID | Log warning, use cost = 0, continue |
| Invalid token count (negative) | Treat as 0, log warning |
| Pricing config unavailable | Use cost = 0, log error |
| Decimal overflow | Cap at maximum value, log error |
| Region not configured | Fall back to ap-northeast-2, log warning |

### API Errors

| Error Scenario | HTTP Status | Response |
|----------------|-------------|----------|
| Invalid time range | 400 | `{"error": "Invalid time range"}` |
| Invalid date format | 400 | `{"error": "Invalid date format"}` |
| Invalid region | 400 | `{"error": "Invalid region"}` |
| Database error | 500 | `{"error": "Internal server error"}` |

### Background Task Errors

```python
async def _record_usage_with_cost(self, ...):
    try:
        # ... cost calculation and recording ...
    except Exception as e:
        # Log error but don't propagate - request already completed
        logger.error(
            "usage_recording_failed",
            error=str(e),
            request_id=ctx.request_id,
            model=model,
        )
        # Optionally: queue for retry or alert
```

## Testing Strategy

### Unit Tests

단위 테스트는 개별 컴포넌트의 정확성을 검증한다:

1. **PricingConfig Tests**
   - Model ID normalization with various Bedrock model ID formats
   - Unknown model handling (returns None)
   - All configured models return valid pricing
   - Region fallback behavior
   - Reload functionality

2. **CostCalculator Tests**
   - Zero token handling
   - Large token counts (up to 10M)
   - Precision verification (6 decimal places)
   - Individual token type calculations
   - Rounding behavior (ROUND_HALF_UP)

3. **API Response Tests**
   - Schema validation
   - Empty data handling
   - Time range filtering
   - KST date range conversion
   - User filtering
   - Cost breakdown aggregation

### Property-Based Tests

Property-based testing을 통해 모든 입력에 대한 정확성을 검증한다. **pytest** with **hypothesis** 라이브러리를 사용한다.

각 property test는 최소 100회 반복 실행하며, 다음 형식의 태그를 포함한다:
`# Feature: cost-visibility, Property N: [property description]`

1. **Property 1 Test**: Model pricing retrieval
   - Generate valid model IDs from known set
   - Verify all price fields are positive Decimals
   - Verify region and effective_date are present

2. **Property 2 Test**: Cost formula correctness
   - Generate random token counts (0 to 10,000,000)
   - Generate random prices (Decimal 0.01 to 100.00)
   - Verify formula: `(tokens / 1M) * price` with 6 decimal precision

3. **Property 3 Test**: Cost aggregation
   - Generate random token combinations for all 4 types
   - Verify total equals sum of individual costs

4. **Property 4 Test**: Usage recording completeness
   - Generate random usage data with cache tokens
   - Mock repository and verify all fields are passed correctly

5. **Property 5 Test**: API response completeness
   - Generate random usage records with costs
   - Verify aggregation correctness in API response

6. **Property 6 Test**: Pricing API completeness
   - Verify all models present in response
   - Verify all required fields present with correct types

7. **Property 7 Test**: Model ID normalization
   - Generate variations of Bedrock model ID strings
   - Verify consistent mapping to pricing keys

8. **Property 8 Test**: Error resilience
   - Generate invalid inputs (unknown models, None pricing)
   - Verify system returns zero costs without exception

9. **Property 9 Test**: Aggregate cache token tracking
   - Generate multiple usage records
   - Verify aggregate sums match individual record sums

10. **Property 10 Test**: KST bucket boundaries
    - Generate timestamps around KST day/week/month boundaries
    - Verify bucket_start aligns with KST and is stored in UTC

### Integration Tests

통합 테스트는 컴포넌트 간 상호작용을 검증한다:

1. **End-to-End Cost Tracking**
   - Proxy request → Background task → DB storage → API retrieval
   - Verify cost consistency across layers

2. **Dashboard Data Flow**
   - API calls → Frontend rendering
   - Verify data transformation correctness

3. **Migration Verification**
   - Verify existing data is preserved after migration
   - Verify new fields have correct default values

4. **KST Range Filtering**
    - Query custom date range in KST
    - Verify UTC conversion and bucket boundaries
