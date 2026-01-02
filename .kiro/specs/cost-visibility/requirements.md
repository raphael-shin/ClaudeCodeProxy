# Requirements Document

## Introduction

Claude 4.5 모델(Opus, Sonnet, Haiku)의 토큰 사용량 기반 비용 가시성을 제공하여 조직의 AI 사용 비용을 추적하고 분석할 수 있도록 한다. 이 기능은 사용자/팀별 예상 비용을 실시간으로 확인하고, 모델별 비용 breakdown을 제공하며, Prompt Caching 비용을 별도로 추적한다. 지원 리전은 ap-northeast-2(Seoul)이며 실제 AWS Bedrock 요금을 기준으로 한다. 요청 처리 시점에 비용을 계산해 Token_Usage에 저장하고, 이후 집계는 저장된 비용을 합산한다.

## Glossary

- **Cost_Calculator**: 토큰 사용량과 모델별 단가를 기반으로 예상 비용을 계산하는 컴포넌트
- **Model_Pricing**: 모델별, 리전별 토큰 단가 정보를 저장하는 데이터 구조
- **Token_Usage**: 요청별 토큰 사용량(input, output, cache write, cache read)을 기록하는 엔티티
- **Usage_Summary_API**: 사용량 및 비용 요약 정보를 제공하는 API 엔드포인트
- **Cost_Dashboard**: 비용 정보를 시각화하여 표시하는 관리자 대시보드 컴포넌트
- **Estimated_Cost**: 토큰 사용량 기반으로 계산된 예상 비용 (USD)
- **Pricing_Snapshot**: 요청 처리 시점에 사용된 모델 단가/리전 정보(비용 고정용)

## Requirements

### Requirement 1: 모델별 요금 관리

**User Story:** As an administrator, I want to manage pricing information for Claude 4.5 models, so that the system can calculate accurate cost estimates.

#### Acceptance Criteria

1. THE Model_Pricing SHALL store unit prices for Claude 4.5 Opus, Sonnet, and Haiku models using their Bedrock model_id values
2. THE Model_Pricing SHALL distinguish prices for input tokens, output tokens, cache write tokens, and cache read tokens
3. WHERE regional pricing differs, THE Model_Pricing SHALL support region-specific prices; initial supported region is ap-northeast-2 (Seoul)
4. WHEN pricing information is updated, THE Cost_Calculator SHALL use the new prices for subsequent calculations without requiring system restart
5. WHEN pricing information is updated, historical Token_Usage costs SHALL remain fixed via Pricing_Snapshot (non-retroactive)

### Requirement 2: 토큰 사용량 확장

**User Story:** As a system operator, I want to track all token types including cache tokens, so that I can have complete visibility into usage patterns.

#### Acceptance Criteria

1. WHEN a request is processed, THE Token_Usage SHALL record cache_creation_input_tokens (cache write tokens)
2. WHEN a request is processed, THE Token_Usage SHALL record cache_read_input_tokens (cache read tokens)
3. WHEN a request is processed, THE Token_Usage SHALL record the model_id used for the request (Bedrock Claude 4.5 Opus/Sonnet/Haiku)
4. WHEN a request is processed, THE Token_Usage SHALL record the region used for pricing (ap-northeast-2)
5. WHEN a request is processed, THE Token_Usage SHALL calculate and store estimated_cost_usd and per-token-type costs (input/output/cache write/cache read)
6. WHEN a request is processed, THE Token_Usage SHALL store Pricing_Snapshot (pricing_id or unit prices used) to keep historical costs fixed

### Requirement 3: 비용 계산 로직

**User Story:** As a system operator, I want accurate cost calculations based on token usage, so that I can provide reliable cost estimates to users.

#### Acceptance Criteria

1. THE Cost_Calculator SHALL calculate cost using the formula: cost = (tokens / 1,000,000) * unit_price_per_million
2. THE Cost_Calculator SHALL calculate costs separately for each token type (input, output, cache write, cache read) and sum them
3. WHEN extracting token information, THE Cost_Calculator SHALL parse the usage field from Bedrock API responses
4. THE Cost_Calculator SHALL maintain precision to 6 decimal places for cost values
5. THE Cost_Calculator SHALL use Pricing_Snapshot (model_id + region + effective price) at the time of Token_Usage capture

### Requirement 4: 사용량 요약 API 확장

**User Story:** As an administrator, I want to retrieve usage summaries with cost information via API, so that I can integrate cost data into monitoring and reporting systems.

#### Acceptance Criteria

1. WHEN the Usage_Summary_API is called, THE System SHALL return total token counts including cache_write_tokens and cache_read_tokens
2. WHEN the Usage_Summary_API is called, THE System SHALL return estimated_cost_usd as the total estimated cost
3. WHEN the Usage_Summary_API is called, THE System SHALL return cost_breakdown showing costs per model (Bedrock Claude 4.5 Opus/Sonnet/Haiku), including cache write/read costs
4. THE Usage_Summary_API SHALL support filtering by time period (day, week, month) or custom date range (YYYY-MM-DD to YYYY-MM-DD)
5. THE Usage_Summary_API SHALL support filtering by user and team
6. THE Usage_Summary_API SHALL aggregate stored Token_Usage costs without recalculating from current pricing

### Requirement 5: 모델 요금 조회 API

**User Story:** As an administrator, I want to retrieve current model pricing information via API, so that I can verify pricing configuration and display it in the dashboard.

#### Acceptance Criteria

1. WHEN GET /api/pricing/models is called, THE System SHALL return pricing information for all configured models
2. THE pricing response SHALL include input_price, output_price, cache_write_price, and cache_read_price for each model
3. THE pricing response SHALL include the model_id for each pricing entry
4. THE pricing response SHALL include region and effective_from (or updated_at) for each pricing entry

### Requirement 6: 대시보드 비용 뷰

**User Story:** As an administrator, I want to view cost information in the dashboard, so that I can monitor and analyze AI usage costs across the organization.

#### Acceptance Criteria

1. WHEN viewing the dashboard, THE Cost_Dashboard SHALL display a summary card showing total estimated cost for the selected period
2. WHEN viewing the dashboard, THE Cost_Dashboard SHALL display a breakdown chart showing costs per model, including cache write/read costs
3. WHEN viewing the dashboard, THE Cost_Dashboard SHALL display a time-series graph showing cost trends over time, including cache write/read costs
4. THE Cost_Dashboard SHALL allow filtering by user/team and time period (day, week, month) or custom date range (YYYY-MM-DD to YYYY-MM-DD)
5. WHEN viewing user details, THE Cost_Dashboard SHALL display that user's cost breakdown by model and token type

### Requirement 7: 비동기 비용 계산

**User Story:** As a system operator, I want cost calculations to not impact request latency, so that the proxy maintains optimal performance.

#### Acceptance Criteria

1. WHEN processing a request, THE Cost_Calculator SHALL perform cost calculations asynchronously after the response is sent
2. THE cost calculation process SHALL NOT add more than 10ms to request processing latency
3. IF cost calculation fails, THEN THE System SHALL log the error and continue without affecting the request response
4. THE asynchronous cost calculation SHALL persist the calculated costs in Token_Usage so later summaries only aggregate stored values

## Reference Pricing (ap-northeast-2, Seoul)

| Model | Input | Output | Cache Write | Cache Read |
|-------|-------|--------|-------------|------------|
| Claude Opus 4.5 | $5.00 | $25.00 | $6.25 | $0.50 |
| Claude Sonnet 4.5 | $3.00 | $15.00 | $3.75 | $0.30 |
| Claude Haiku 4.5 | $1.00 | $5.00 | $1.25 | $0.10 |

*단위: USD per 1M tokens*

### Long Context Pricing (Sonnet 4.5 only)

| Token Type | Price |
|------------|-------|
| Input (Long Context) | $6.00 |
| Output (Long Context) | $22.50 |
| Cache Write (Long Context) | $7.50 |
| Cache Read (Long Context) | $0.60 |

*단위: USD per 1M tokens*

## Out of Scope

- 실시간 AWS Pricing API 연동 (수동 업데이트로 시작)
- 청구서 생성 기능
- 결제 시스템 연동
- Provisioned Throughput 요금 계산
- 비용 알림 임계값 설정
- 예산 초과 경고
- 비용 예측 기능
