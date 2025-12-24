# Business Logic Model - Unit 1E: Usage Metering & Observability

## 설계 원칙

- PostgreSQL에는 Bedrock token_usage만 저장
- 요청 로그/디버깅은 CloudWatch Logs로 해결 (request_id 기반 조회)
- CloudWatch Metrics로 실시간 모니터링

---

## Usage Recording Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Usage Recording Flow                          │
└─────────────────────────────────────────────────────────────────┘

    ProxyResponse (from Router)
                │
                ▼
       ┌────────────────┐
       │ Emit Structured│
       │ Log (always)   │
       │ → CloudWatch   │
       └───────┬────────┘
               │
               ▼
       ┌────────────────────┐
       │ Is Bedrock Success?│
       └─────────┬──────────┘
                 │
        ┌────────┴────────┐
        │                 │
       Yes               No
        │                 │
        ▼                 │
┌────────────────┐        │
│ Build Token    │        │
│ Usage Record   │        │
└───────┬────────┘        │
        │                 │
        ▼                 │
┌────────────────┐        │
│ Insert to      │        │
│ token_usage    │        │
│ (async)        │        │
└───────┬────────┘        │
        │                 │
        └────────┬────────┘
                 │
                 ▼
        ┌────────────────┐
        │ Emit Metrics   │
        │ (CloudWatch)   │
        └────────────────┘
```

---

## CloudWatch Structured Logging

### Log Schema (모든 요청)

```python
logger.info(
    "request_completed",
    request_id=ctx.request_id,
    access_key_prefix=ctx.access_key_prefix,
    provider_attempted=providers_tried,      # ["plan", "bedrock"]
    provider_used=response.provider,
    is_fallback=response.is_fallback,
    status_code=response.status_code,
    error_type=response.error_type,
    latency_ms=latency,
    model=request.model
)
```

### Recording Rules
- **Always recorded** for every request (Plan, Bedrock, 성공, 실패 모두)
- Recorded **after** response is determined
- **Async** emission (non-blocking)
- **Immutable** after creation

---

## Token Usage Schema (DB 저장)

```python
@dataclass
class TokenUsageRecord:
    id: str                              # UUID
    request_id: str                      # UNIQUE, 로그 상관관계
    timestamp: datetime                  # TIMESTAMPTZ
    user_id: str                        # User reference
    access_key_id: str                  # Key used
    model: str                          # Model used
    input_tokens: int                   # Input count
    output_tokens: int                  # Output count
    cache_read_input_tokens: int | None # Cache read
    cache_creation_input_tokens: int | None # Cache creation
    total_tokens: int                   # Computed sum
    provider: str                       # 항상 "bedrock"
    is_fallback: bool                   # Plan 실패 후 Bedrock 사용 여부
    latency_ms: int                     # Bedrock 요청 지연시간
```

### Recording Rules
- **Only for successful Bedrock requests**
- **NOT recorded** for Plan requests (CloudWatch Logs만)
- **NOT recorded** for failed requests (CloudWatch Logs만)
- **Async** insertion (non-blocking, bounded queue 권장)
- `UNIQUE(request_id)` 제약

---

## CloudWatch Metrics

### Metric Definitions

| Metric Name | Dimensions | Unit | Description |
|-------------|------------|------|-------------|
| RequestCount | Provider (plan/bedrock) | Count | Requests per provider |
| RequestLatency | Provider | Milliseconds | p50, p95, p99 latency |
| ErrorCount | ErrorType, Provider | Count | Errors by type and provider |
| FallbackCount | - | Count | Fallback events |
| CircuitOpen | - | Count | Circuit open events |
| BedrockTokensUsed | TokenType (input/output) | Count | Tokens by type |

### Metric Emission

```python
async def emit_metrics(response: ProxyResponse, latency_ms: int):
    # Request count (provider dimension)
    await cloudwatch.put_metric(
        MetricName="RequestCount",
        Dimensions=[{"Name": "Provider", "Value": response.provider}],
        Value=1, Unit="Count"
    )
    
    # Latency (provider dimension)
    await cloudwatch.put_metric(
        MetricName="RequestLatency",
        Dimensions=[{"Name": "Provider", "Value": response.provider}],
        Value=latency_ms, Unit="Milliseconds"
    )
    
    # Error count (error_type + provider dimensions)
    if response.error_type:
        await cloudwatch.put_metric(
            MetricName="ErrorCount",
            Dimensions=[
                {"Name": "ErrorType", "Value": response.error_type},
                {"Name": "Provider", "Value": response.provider}
            ],
            Value=1, Unit="Count"
        )
    
    # Fallback count
    if response.is_fallback:
        await cloudwatch.put_metric(
            MetricName="FallbackCount",
            Value=1, Unit="Count"
        )
    
    # Token usage (Bedrock only)
    if response.provider == "bedrock" and response.usage:
        await cloudwatch.put_metric(
            MetricName="BedrockTokensUsed",
            Dimensions=[{"Name": "TokenType", "Value": "input"}],
            Value=response.usage.input_tokens, Unit="Count"
        )
        await cloudwatch.put_metric(
            MetricName="BedrockTokensUsed",
            Dimensions=[{"Name": "TokenType", "Value": "output"}],
            Value=response.usage.output_tokens, Unit="Count"
        )
```

---

## Aggregation Logic

### Rollup Schedule

| Bucket Type | Source | Schedule | Retention |
|-------------|--------|----------|-----------|
| minute | token_usage | Real-time | 14 days |
| hour | minute buckets | Every hour | Indefinite |
| day | hour buckets | Daily | Indefinite |
| month | day buckets | Monthly | Indefinite |

### Aggregation Query

```sql
-- Minute rollup (real-time insert trigger or batch)
-- total_requests = Bedrock 사용 횟수 (token_usage row count)
INSERT INTO usage_aggregates (
    bucket_type, bucket_start, user_id, access_key_id,
    total_requests, total_input_tokens, total_output_tokens, total_tokens
)
SELECT 
    'minute',
    date_trunc('minute', timestamp),
    user_id,
    access_key_id,
    COUNT(*),
    SUM(input_tokens),
    SUM(output_tokens),
    SUM(total_tokens)
FROM token_usage
WHERE timestamp >= :start AND timestamp < :end
GROUP BY date_trunc('minute', timestamp), user_id, access_key_id
ON CONFLICT (bucket_type, bucket_start, user_id, access_key_id)
DO UPDATE SET
    total_requests = EXCLUDED.total_requests,
    total_input_tokens = EXCLUDED.total_input_tokens,
    total_output_tokens = EXCLUDED.total_output_tokens,
    total_tokens = EXCLUDED.total_tokens;
```

---

## Dashboard Query Interface

### Query Parameters

```python
@dataclass
class UsageQuery:
    user_id: str | None           # Filter by user
    access_key_id: str | None     # Filter by key
    bucket_type: str              # minute|hour|day|month
    start_time: datetime          # Range start
    end_time: datetime            # Range end
```

### Query Response

```python
@dataclass
class UsageResult:
    buckets: list[UsageBucket]
    total_requests: int           # = Bedrock 사용 횟수
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int

@dataclass
class UsageBucket:
    bucket_start: datetime
    requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
```

---

## CloudWatch Logs Insights 쿼리 템플릿

### 요청 추적 (request_id 기반)
```sql
fields @timestamp, request_id, provider_used, is_fallback, status_code, latency_ms
| filter request_id = "req_abc123"
| sort @timestamp desc
```

### 키별 Fallback 분석
```sql
fields @timestamp, access_key_prefix, is_fallback
| filter is_fallback = true
| stats count() as fallback_count by access_key_prefix
| sort fallback_count desc
```

### 에러 분석
```sql
fields @timestamp, request_id, error_type, provider_used
| filter error_type != ""
| stats count() as error_count by error_type, provider_used
| sort error_count desc
```

### Provider별 지연시간 분석
```sql
fields @timestamp, provider_used, latency_ms
| stats avg(latency_ms) as avg_latency, 
        pct(latency_ms, 95) as p95_latency,
        pct(latency_ms, 99) as p99_latency
  by provider_used
```
