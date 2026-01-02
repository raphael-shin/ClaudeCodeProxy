# Implementation Plan: Cost Visibility

## Overview

Claude 4.5 모델의 토큰 사용량 기반 비용 가시성 기능을 구현한다. 데이터베이스 스키마 확장, 비용 계산 로직, API 확장, 프론트엔드 대시보드 통합 순서로 진행한다. KST(UTC+9) 기준 기간 필터/버킷 경계와 Pricing_Snapshot 저장을 포함한다.

## Tasks

- [x] 1. Set up pricing domain and cost calculator
  - [x] 1.1 Create pricing configuration module
    - Create `backend/src/domain/pricing.py` with `ModelPricing` dataclass and `PricingConfig` class
    - Implement model ID normalization for Bedrock model IDs
    - Support `PROXY_MODEL_PRICING` environment variable for runtime configuration
    - Implement `PricingConfig.reload()` and JSON loader for config updates
    - Default region: ap-northeast-2
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x]* 1.2 Write property test for model pricing retrieval
    - **Property 1: Model Pricing Storage and Retrieval**
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [x] 1.3 Create cost calculator module
    - Create `backend/src/domain/cost_calculator.py` with `CostBreakdown` dataclass and `CostCalculator` class
    - Implement formula: `cost = (tokens / 1,000,000) * price_per_million`
    - Maintain 6 decimal precision with ROUND_HALF_UP
    - _Requirements: 3.1, 3.4_

  - [x]* 1.4 Write property tests for cost calculator
    - **Property 2: Cost Calculation Formula Correctness**
    - **Property 3: Cost Aggregation Correctness**
    - **Validates: Requirements 3.1, 3.2, 3.4**

  - [x]* 1.5 Write property test for model ID normalization
    - **Property 7: Model ID Normalization Consistency**
    - **Validates: Requirements 1.1, 3.3**

- [x] 2. Database schema migration
  - [x] 2.1 Create Alembic migration for token_usage table
    - Add columns: `estimated_cost_usd`, `input_cost_usd`, `output_cost_usd`, `cache_write_cost_usd`, `cache_read_cost_usd`, `pricing_region`
    - Add pricing snapshot columns: `pricing_model_id`, `pricing_effective_date`, `pricing_input_price_per_million`, `pricing_output_price_per_million`, `pricing_cache_write_price_per_million`, `pricing_cache_read_price_per_million`
    - All cost columns: DECIMAL(12, 6) NOT NULL DEFAULT 0
    - pricing_region: VARCHAR(32) NOT NULL DEFAULT 'ap-northeast-2'
    - _Requirements: 2.4_

  - [x] 2.2 Create Alembic migration for usage_aggregates table
    - Add columns: `total_cache_write_tokens`, `total_cache_read_tokens`
    - Add cost totals: `total_input_cost_usd`, `total_output_cost_usd`, `total_cache_write_cost_usd`, `total_cache_read_cost_usd`, `total_estimated_cost_usd`
    - Cache token columns: BIGINT NOT NULL DEFAULT 0
    - Cost columns: DECIMAL(15, 6) NOT NULL DEFAULT 0
    - _Requirements: 4.1, 4.2_

  - [x] 2.3 Update SQLAlchemy models
    - Update `TokenUsageModel` with cost, region, and pricing snapshot fields
    - Update `UsageAggregateModel` with cache token and cost total fields
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 3. Checkpoint - Verify migrations
  - Run `alembic upgrade head` and verify schema changes
  - Ensure all tests pass, ask the user if questions arise

- [x] 4. Extend usage recording with cost calculation
  - [x] 4.1 Update TokenUsageRepository
    - Add new parameters to `create()` method for cost fields
    - Add pricing snapshot fields to `create()` method
    - Update `_to_entity()` to include new fields
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 4.2 Update UsageAggregateRepository
    - Add cache token and cost parameters to `increment()` method
    - Add cost total parameters (input/output/cache write/cache read)
    - Update `query_bucket_totals()` to include new fields
    - Update `get_totals()` to include new fields
    - _Requirements: 4.1, 4.2_

  - [x] 4.3 Update domain entities
    - Add cost fields to `TokenUsage` entity
    - Add cache token and cost fields to `UsageAggregate` entity
    - _Requirements: 2.4_

  - [x] 4.4 Modify UsageRecorder for background cost calculation
    - Import pricing and cost calculator modules
    - Implement `_record_usage_with_cost()` as background task
    - Use `asyncio.create_task()` for non-blocking execution
    - Implement `_calculate_cost_safe()` with error handling
    - Store Pricing_Snapshot fields and `pricing_model_id` (normalized)
    - Use KST(UTC+9) bucket boundaries with Sunday week start
    - _Requirements: 2.4, 3.1, 3.2, 3.3, 7.1, 7.2, 7.3_

  - [x]* 4.5 Write property test for usage recording completeness
    - **Property 4: Token Usage Recording Completeness**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

  - [x]* 4.6 Write property test for error resilience
    - **Property 8: Error Resilience**
    - **Validates: Requirements 7.3**

  - [x]* 4.7 Write property test for aggregate cache token + cost totals
    - **Property 9: Aggregate Cache Token Tracking**
    - **Validates: Requirements 4.1, 4.2**

  - [x]* 4.8 Write property test for KST bucket boundaries
    - **Property 10: KST Bucket Boundaries**
    - Sunday start for week buckets (KST)
    - **Validates: Requirements 4.4**

- [x] 5. Checkpoint - Verify backend cost tracking
  - Run backend tests to verify cost calculation and recording
  - Ensure all tests pass, ask the user if questions arise

- [x] 6. Extend Usage API with cost information
  - [x] 6.1 Update API response schemas
    - Add `CostBreakdownByModel` schema
    - Update `UsageBucket` with cache tokens and token-type cost fields (`*_cost_usd`)
    - Update `UsageResponse` with cache totals, token-type cost totals, and cost breakdown
    - Use string type for cost values to preserve precision
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 6.2 Update admin_usage.py endpoint
    - Modify `get_usage()` to include cost information in response
    - Add cost breakdown by model + token type aggregation logic (by `pricing_model_id`)
    - Support user_id, team_id, and time period/custom date range (YYYY-MM-DD) filtering
    - Use KST boundaries (Sunday week start) and convert to UTC for queries
    - Apply team_id filter via user-team mapping join
    - Do not reprice; aggregate stored costs only
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x]* 6.3 Write property test for usage summary API
    - **Property 5: Usage Summary API Response Completeness**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [x] 7. Create Pricing API endpoint
  - [x] 7.1 Create admin_pricing.py router
    - Create `backend/src/api/admin_pricing.py`
    - Implement `GET /api/pricing/models` endpoint
    - Implement `POST /api/pricing/reload` endpoint
    - Return all configured models with pricing info
    - Include region and effective_date in response
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 7.2 Register pricing router in main.py
    - Import and include pricing router
    - _Requirements: 5.1_

  - [x]* 7.3 Write property test for pricing API
    - **Property 6: Pricing API Response Completeness**
    - **Validates: Requirements 5.1, 5.2, 5.3**

- [x] 8. Checkpoint - Verify API endpoints
  - Test API endpoints manually or with integration tests
  - Ensure all tests pass, ask the user if questions arise

- [x] 9. Frontend API client updates
  - [x] 9.1 Update api.ts with new types and endpoints
    - Add `ModelPricing`, `CostBreakdownByModel`, `UsageCostResponse` types
    - Add `getModelPricing()` function
    - Add `reloadPricing()` function (admin only)
    - Update `UsageResponse` type with cost fields
    - _Requirements: 4.1, 5.1, 6.1_

- [x] 10. Dashboard cost visualization
  - [x] 10.1 Add cost summary card to UsagePage
    - Display total estimated cost for selected period
    - Format as USD with appropriate precision
    - _Requirements: 6.1_

  - [x] 10.2 Add model cost breakdown chart
    - Create pie or bar chart showing cost per model
    - Show token-type costs per model (stacked bars or tooltip breakdown)
    - Use recharts library (already in project)
    - _Requirements: 6.2_

  - [x] 10.3 Add cost trend to time-series graph
    - Add cost line to existing token trend chart
    - Use secondary Y-axis for cost values
    - _Requirements: 6.3_

  - [x] 10.4 Update user detail view with cost breakdown
    - Show user's cost breakdown by model + token type
    - Display cache token usage and cache cost
    - _Requirements: 6.4, 6.5_

- [x] 11. Final checkpoint - End-to-end verification
  - Verify complete flow: request → cost calculation → API → dashboard
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional property-based tests
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests use pytest with hypothesis library
- All cost values use Decimal for precision, string for API responses
