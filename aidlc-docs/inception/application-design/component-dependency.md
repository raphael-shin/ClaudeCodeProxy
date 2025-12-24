# Component Dependencies - ClaudeCodeProxy

## Dependency Matrix

| Component | Depends On | Depended By |
|-----------|------------|-------------|
| **1A: Ingress & Auth** | AccessKeyRepository, AccessKeyCache, KeyHasher | Router (1D) |
| **1B: Plan Adapter** | HTTP Client, Config | Router (1D) |
| **1C: Bedrock Adapter** | HTTP Client, BedrockKeyService | Router (1D) |
| **1D: Router** | 1B, 1C, CircuitBreaker | ProxyService (orchestration) |
| **1E: Usage Metering** | RequestLogRepo, TokenUsageRepo, MetricsEmitter | ProxyService (orchestration) |
| **2: Admin Backend** | All Repositories, Services | 3: Admin Frontend |
| **3: Admin Frontend** | 2: Admin Backend API | None |
| **4: Infrastructure** | None | All (runtime) |

**Note**: ProxyService is an orchestration layer, not a unit. It coordinates Units 1A-1E.

---

## Communication Patterns

### Proxy Request Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                         HTTP Request                              │
│                    POST /ak/{key}/v1/messages                     │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Unit 1A: Ingress & Auth                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │ Extract Key │───▶│ Check Cache │───▶│ Validate DB │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
│                                │                                  │
│                                ▼                                  │
│                       RequestContext                              │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Unit 1D: Router                                │
│  ┌─────────────────┐                                             │
│  │ Check Circuit   │                                             │
│  │ Breaker State   │                                             │
│  └────────┬────────┘                                             │
│           │                                                       │
│     ┌─────┴─────┐                                                │
│     ▼           ▼                                                │
│  CLOSED      OPEN                                                │
│     │           │                                                │
│     ▼           ▼                                                │
│  Try Plan    Skip Plan                                           │
└──────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│   Unit 1B: Plan Adapter   │   │  Unit 1C: Bedrock Adapter │
│  ┌─────────────────────┐  │   │  ┌─────────────────────┐  │
│  │ Transform Request   │  │   │  │ Get Bedrock Key     │  │
│  │ Call Anthropic API  │  │   │  │ Transform to Converse│  │
│  │ Parse Response      │  │   │  │ Call Bedrock API    │  │
│  └─────────────────────┘  │   │  │ Transform Response  │  │
└───────────────────────────┘   │  └─────────────────────┘  │
                │               └───────────────────────────┘
                │                               │
                └───────────────┬───────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Unit 1E: Usage Metering                        │
│  ┌─────────────────┐    ┌─────────────────┐                      │
│  │ Record Usage    │    │ Emit Metrics    │                      │
│  │ (Bedrock only)  │    │ (CloudWatch)    │                      │
│  └─────────────────┘    └─────────────────┘                      │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                         HTTP Response                             │
│                    Anthropic-compatible JSON                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

### Access Key Validation Flow

```
┌─────────┐     ┌─────────┐     ┌──────────────┐     ┌──────────┐
│ Request │────▶│  Cache  │────▶│ AccessKey DB │────▶│ Context  │
└─────────┘     └─────────┘     └──────────────┘     └──────────┘
     │               │                  │                  │
     │          cache hit          cache miss              │
     │               │                  │                  │
     │               ▼                  ▼                  │
     │         Return ctx         Query + Cache            │
     │                                  │                  │
     │                                  ▼                  │
     │                            Return ctx               │
     └─────────────────────────────────────────────────────┘
```

### Bedrock Key Retrieval Flow (with Cache)

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────┐     ┌──────────┐
│ Access Key  │────▶│ BedrockKey   │────▶│ BedrockKey   │────▶│   KMS   │────▶│ Decrypted│
│     ID      │     │    Cache     │     │   Repository │     │ Decrypt │     │   Key    │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────┘     └──────────┘
                          │                                                         │
                     cache hit                                                      │
                          │                                                         │
                          ▼                                                         │
                    Return cached                                              cache set
                    (skip KMS)                                                      │
                                                                                    ▼
                                                                              Return + cache
```

**Cache Invalidation Points**:
- `BedrockKeyService.register_key()` → invalidate
- `BedrockKeyService.rotate_key()` → invalidate
- `BedrockKeyService.revoke_key()` → invalidate
- `AccessKeyService.revoke_key()` → invalidate both caches

### Usage Recording Flow (Separated Logs)

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Response   │────▶│ RequestLog   │────▶│ RequestLog   │
│  (Any)      │     │   Builder    │     │   DB Table   │
└─────────────┘     └──────────────┘     └──────────────┘
                           │                    │
                           │              Always recorded
                           │              (Plan + Bedrock)
                           │
                           ▼
                    ┌──────────────┐
                    │  CloudWatch  │
                    │   Metrics    │
                    └──────────────┘

┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Response   │────▶│ TokenUsage   │────▶│ TokenUsage   │
│  (Bedrock   │     │   Builder    │     │   DB Table   │
│   Success)  │     └──────────────┘     └──────────────┘
└─────────────┘                                │
                                         Bedrock only
                                         (tokens tracked)
```

**Logging Strategy**:
- `request_logs` table: Always recorded (Plan + Bedrock outcomes)
- `token_usage` table: Bedrock successful requests only
- CloudWatch metrics: Both providers (counts, latency, fallback rate)

---

## Interface Contracts

### Between 1A and 1D

```python
# 1A produces RequestContext
@dataclass
class RequestContext:
    request_id: str
    user_id: str
    access_key_id: str
    bedrock_region: str
    bedrock_model: str
    has_bedrock_key: bool
    timestamp: datetime

# 1D consumes RequestContext
class Router:
    async def route(self, ctx: RequestContext, request: AnthropicRequest) -> ProxyResponse:
        ...
```

### Between 1D and 1B/1C

```python
# Shared protocol for adapters
class UpstreamAdapter(Protocol):
    async def invoke(
        self, 
        ctx: RequestContext, 
        request: AnthropicRequest
    ) -> AdapterResponse | AdapterError:
        ...

# 1D calls adapters through protocol
class Router:
    def __init__(self, plan_adapter: UpstreamAdapter, bedrock_adapter: UpstreamAdapter):
        ...
```

### Between 1D and 1E

```python
# 1D produces response with metadata
@dataclass
class ProxyResponse:
    is_success: bool
    provider: str  # "plan" | "bedrock"
    is_fallback: bool
    response: AdapterResponse | None
    error: AdapterError | None

# 1E consumes response for metering
class UsageRecorder:
    async def record_async(self, record: UsageRecord) -> None:
        ...
```

---

## Dependency Injection Structure

```python
# Dependency provider functions (unified DI style)
def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    ...

def get_key_hasher() -> KeyHasher:
    """HMAC-based key hasher with server secret from Secrets Manager."""
    server_secret = get_secret("key-hasher-secret")
    return KeyHasher(server_secret)

def get_access_key_cache() -> AccessKeyCache:
    """In-memory cache for access key lookups (TTL: 60s)."""
    return AccessKeyCache(ttl_seconds=60)

def get_bedrock_key_cache() -> BedrockKeyCache:
    """In-memory cache for decrypted Bedrock keys (TTL: 300s)."""
    return BedrockKeyCache(ttl_seconds=300)

def get_validator(
    db: AsyncSession = Depends(get_db),
    cache: AccessKeyCache = Depends(get_access_key_cache),
    hasher: KeyHasher = Depends(get_key_hasher)
) -> AccessKeyValidator:
    repo = AccessKeyRepository(db)
    return AccessKeyValidator(repo, cache, hasher)

def get_bedrock_key_service(
    db: AsyncSession = Depends(get_db),
    cache: BedrockKeyCache = Depends(get_bedrock_key_cache),
    hasher: KeyHasher = Depends(get_key_hasher)
) -> BedrockKeyService:
    repo = BedrockKeyRepository(db)
    kms = KMSClient()
    return BedrockKeyService(repo, kms, hasher, cache)

def get_router(
    bedrock_key_service: BedrockKeyService = Depends(get_bedrock_key_service)
) -> Router:
    # PlanAdapter forwards client auth headers by default; optional default key.
    plan_adapter = PlanAdapter(
        api_key=get_secret_optional("plan-api-key"),
        headers=request_headers
    )
    bedrock_adapter = BedrockAdapter(bedrock_key_service)
    circuit_breaker = CircuitBreaker(failure_threshold=3, reset_timeout=1800)
    return Router(plan_adapter, bedrock_adapter, circuit_breaker)

def get_usage_recorder(
    db: AsyncSession = Depends(get_db)
) -> UsageRecorder:
    request_log_repo = RequestLogRepository(db)
    token_usage_repo = TokenUsageRepository(db)
    return UsageRecorder(request_log_repo, token_usage_repo)

def get_proxy_service(
    router: Router = Depends(get_router),
    usage_recorder: UsageRecorder = Depends(get_usage_recorder)
) -> ProxyService:
    metrics = MetricsEmitter(CloudWatchClient())
    return ProxyService(router, usage_recorder, metrics)

# FastAPI route using unified DI
@router.post("/ak/{access_key}/v1/messages")
async def handle_messages(
    access_key: str,
    request: AnthropicRequest,
    validator: AccessKeyValidator = Depends(get_validator),
    proxy_service: ProxyService = Depends(get_proxy_service)
) -> Response:
    # Validate access key
    ctx = await validator.validate(access_key)
    if not ctx:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    
    # Handle request
    response = await proxy_service.handle_request(ctx, request)
    return response.to_http_response()
```

**DI Style**: All dependencies use `Depends()` pattern for consistency and testability.

---

## External Dependencies

| Component | External Service | Purpose |
|-----------|-----------------|---------|
| 1B: Plan Adapter | Anthropic API | Plan upstream calls |
| 1C: Bedrock Adapter | Amazon Bedrock | Fallback LLM calls |
| 1C: Bedrock Adapter | AWS KMS | Key decryption |
| 1E: Usage Metering | Amazon CloudWatch | Metrics emission |
| 2: Admin Backend | AWS Secrets Manager | Admin credentials |
| 4: Infrastructure | AWS (ECS, Aurora, ALB, etc.) | Runtime platform |

---

## Build-Time Dependencies

```
claude-code-proxy/
├── src/
│   ├── shared/          # No external deps within project
│   │   ├── models/
│   │   ├── repositories/
│   │   └── utils/
│   │
│   ├── proxy/           # Depends on: shared
│   │   ├── adapters/
│   │   ├── routing/
│   │   └── metering/
│   │
│   └── admin/           # Depends on: shared
│       ├── services/
│       └── api/
│
├── admin-ui/            # Depends on: admin API (runtime)
│   └── ...
│
└── infra/               # No code deps, defines runtime env
    └── ...
```

### Python Package Dependencies

```
shared/
├── sqlalchemy
├── pydantic
└── boto3

proxy/
├── shared (internal)
├── fastapi
├── httpx
└── uvicorn

admin/
├── shared (internal)
├── fastapi
├── uvicorn
└── python-jose (JWT)
```
