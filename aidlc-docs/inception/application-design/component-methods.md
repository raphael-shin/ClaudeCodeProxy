# Component Methods - ClaudeCodeProxy

## Shared Types

### Error Type Enum (Fixed)

```python
class PlanErrorType(str, Enum):
    """Plan upstream error classifications."""
    RATE_LIMIT = "rate_limit"           # HTTP 429
    USAGE_LIMIT = "usage_limit"         # Usage/quota exceeded (may be 429 or other)
    SERVER_ERROR = "server_error"       # HTTP 5xx
    CLIENT_ERROR = "client_error"       # HTTP 4xx (non-429)
    TIMEOUT = "timeout"                 # Request timeout
    NETWORK_ERROR = "network_error"     # Connection failed

class BedrockErrorType(str, Enum):
    """Bedrock error classifications."""
    AUTH_ERROR = "bedrock_auth_error"           # AccessDeniedException
    QUOTA_EXCEEDED = "bedrock_quota_exceeded"   # ThrottlingException
    UNAVAILABLE = "bedrock_unavailable"         # ServiceUnavailable, timeout
    VALIDATION_ERROR = "bedrock_validation"     # ValidationException
    MODEL_ERROR = "bedrock_model_error"         # ModelError

# Circuit breaker triggers ONLY on these Plan error types
CIRCUIT_BREAKER_TRIGGERS = {PlanErrorType.RATE_LIMIT, PlanErrorType.SERVER_ERROR}
```

### Request Context

```python
@dataclass
class RequestContext:
    request_id: str
    user_id: str
    access_key_id: str
    bedrock_region: str
    bedrock_model: str
    has_bedrock_key: bool
    received_at: datetime      # Server received timestamp
    request_started_at: datetime | None = None  # Routing/upstream call start
```

### Anthropic Request/Response (Passthrough Strategy)

```python
@dataclass
class ContentBlock:
    """Anthropic content block - supports text, tool_use, tool_result."""
    type: str  # "text", "tool_use", "tool_result"
    text: str | None = None
    # Tool fields preserved as-is for passthrough
    id: str | None = None
    name: str | None = None
    input: dict | None = None
    tool_use_id: str | None = None
    content: Any | None = None  # For tool_result

@dataclass
class AnthropicRequest:
    model: str
    messages: list[dict]  # Passthrough - preserve structure
    max_tokens: int
    # Preserve all other fields for passthrough
    system: str | list | None = None
    tools: list[dict] | None = None
    tool_choice: dict | None = None
    metadata: dict | None = None
    stop_sequences: list[str] | None = None
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None

@dataclass
class AdapterResponse:
    id: str
    type: str  # "message"
    role: str  # "assistant"
    content: list[ContentBlock]  # Multiple content blocks supported
    model: str
    stop_reason: str | None
    stop_sequence: str | None
    usage: TokenUsage

@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None

@dataclass
class AdapterError:
    error_type: PlanErrorType | BedrockErrorType
    message: str
    status_code: int
    retryable: bool
    raw_error: dict | None = None  # Preserve original error for debugging
```

### Key Security Types

```python
@dataclass
class KeyHashConfig:
    """HMAC-based key hashing configuration."""
    algorithm: str = "sha256"
    # Server secret loaded from Secrets Manager - NEVER hardcoded
    # hash = HMAC-SHA256(server_secret, raw_key)

@dataclass
class MaskingRules:
    """Key masking rules for display."""
    # Access Key: ak_ + first 6 chars visible
    # Example: ak_6D3h3X... (showing ak_ + 6 chars + ...)
    access_key_visible_chars: int = 6
    
    # Bedrock Key: Show "Registered" or "Not Registered" only
    # Never show any portion of Bedrock API Key
    bedrock_key_display: str = "status_only"  # "status_only" | "prefix_only"
```

---

## Unit 1A: Request Ingress & Authentication

### Protocol

```python
class AccessKeyValidator(Protocol):
    async def validate(self, access_key: str) -> RequestContext | None:
        """Validate access key and return context, or None if invalid."""
        ...
```

### Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `validate` | `access_key: str` | `RequestContext \| None` | Validate key, return context or None |
| `get_cached` | `access_key: str` | `RequestContext \| None` | Check in-memory cache first |
| `invalidate_cache` | `access_key: str` | `None` | Remove key from cache |

### IngressHandler (FastAPI)

```python
@router.post("/ak/{access_key}/v1/messages")
async def handle_messages(
    access_key: str,
    request: AnthropicRequest,
    validator: AccessKeyValidator = Depends(),
    router: Router = Depends()
) -> Response:
    ...
```

---

## Unit 1B: Plan Upstream Adapter

### Protocol

```python
class UpstreamAdapter(Protocol):
    async def invoke(
        self, 
        ctx: RequestContext, 
        request: AnthropicRequest
    ) -> AdapterResponse | AdapterError:
        """Invoke upstream and return response or error."""
        ...
```

### Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `invoke` | `ctx`, `request` | `AdapterResponse \| AdapterError` | Call Plan upstream |
| `_transform_request` | `AnthropicRequest` | `dict` | Transform to API format |
| `_parse_response` | `httpx.Response` | `AdapterResponse` | Parse success response |
| `_classify_error` | `httpx.Response` | `AdapterError` | Classify error type |

### Error Classification

```python
def _classify_error(self, response: httpx.Response) -> AdapterError:
    if response.status_code == 429:
        # Check if rate_limit or usage_limit based on error body
        body = response.json()
        if "usage" in body.get("error", {}).get("type", "").lower():
            return AdapterError(PlanErrorType.USAGE_LIMIT, ..., retryable=True)
        return AdapterError(PlanErrorType.RATE_LIMIT, ..., retryable=True)
    if response.status_code >= 500:
        return AdapterError(PlanErrorType.SERVER_ERROR, ..., retryable=True)
    if response.status_code >= 400:
        return AdapterError(PlanErrorType.CLIENT_ERROR, ..., retryable=False)
    # ... other classifications
```

---

## Unit 1C: Bedrock Adapter

### Protocol

Implements `UpstreamAdapter` protocol (same as Unit 1B).

### Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `invoke` | `ctx`, `request` | `AdapterResponse \| AdapterError` | Call Bedrock Converse |
| `_get_bedrock_key` | `access_key_id` | `str` | Decrypt Bedrock API Key |
| `_transform_to_converse` | `AnthropicRequest` | `ConverseRequest` | Transform to Bedrock format |
| `_transform_from_converse` | `ConverseResponse` | `AdapterResponse` | Transform to Anthropic format |
| `_extract_usage` | `ConverseResponse` | `TokenUsage` | Extract token counts |
| `_classify_error` | `Exception` | `AdapterError` | Classify Bedrock errors |

### Error Classification

```python
def _classify_error(self, error: Exception) -> AdapterError:
    error_str = str(error)
    if "AccessDeniedException" in error_str:
        return AdapterError(BedrockErrorType.AUTH_ERROR, ...)
    if "ThrottlingException" in error_str:
        return AdapterError(BedrockErrorType.QUOTA_EXCEEDED, ...)
    if "ValidationException" in error_str:
        return AdapterError(BedrockErrorType.VALIDATION_ERROR, ...)
    if "ModelError" in error_str:
        return AdapterError(BedrockErrorType.MODEL_ERROR, ...)
    return AdapterError(BedrockErrorType.UNAVAILABLE, ...)
```

---

## Unit 1D: Routing & Circuit Breaker

### Router Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `route` | `ctx`, `request` | `ProxyResponse` | Execute routing logic |
| `_should_skip_plan` | `access_key_id` | `bool` | Check circuit state |
| `_try_plan` | `ctx`, `request` | `AdapterResponse \| AdapterError` | Attempt Plan call |
| `_try_bedrock` | `ctx`, `request` | `AdapterResponse \| AdapterError` | Attempt Bedrock call |
| `_handle_plan_failure` | `access_key_id`, `error` | `None` | Update circuit state |

### CircuitBreaker Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `is_open` | `access_key_id` | `bool` | Check if circuit is open |
| `record_failure` | `access_key_id` | `None` | Record Plan failure |
| `record_success` | `access_key_id` | `None` | Record Plan success |
| `reset` | `access_key_id` | `None` | Reset circuit state |
| `get_state` | `access_key_id` | `CircuitState` | Get current state |

### Routing Logic

```python
async def route(self, ctx: RequestContext, request: AnthropicRequest) -> ProxyResponse:
    ctx.request_started_at = datetime.utcnow()
    
    # Check circuit state
    if self.circuit.is_open(ctx.access_key_id):
        if ctx.has_bedrock_key:
            return await self._try_bedrock(ctx, request)
        else:
            return ProxyResponse.error(503, "Service unavailable - circuit open, no Bedrock configured")
    
    # Try Plan first
    result = await self._try_plan(ctx, request)
    if isinstance(result, AdapterResponse):
        self.circuit.record_success(ctx.access_key_id)
        return ProxyResponse.success(result, provider="plan", is_fallback=False)
    
    # Plan failed - check if circuit breaker trigger condition
    # ONLY rate_limit (429) and server_error (5xx) trigger circuit breaker
    if result.error_type in CIRCUIT_BREAKER_TRIGGERS:
        self.circuit.record_failure(ctx.access_key_id)
    
    # Check if should fallback to Bedrock
    if result.retryable and ctx.has_bedrock_key:
        bedrock_result = await self._try_bedrock(ctx, request)
        if isinstance(bedrock_result, AdapterResponse):
            return ProxyResponse.success(bedrock_result, provider="bedrock", is_fallback=True)
        return ProxyResponse.error_from_adapter(bedrock_result)
    
    # No fallback available
    if not ctx.has_bedrock_key:
        return ProxyResponse.error(503, "Plan unavailable, no Bedrock configured")
    
    return ProxyResponse.error_from_adapter(result)
```

### Circuit Breaker Policy Table

| Error Type | Triggers Circuit | Allows Fallback |
|------------|------------------|-----------------|
| `rate_limit` (429) | ✅ Yes | ✅ Yes |
| `usage_limit` | ❌ No | ✅ Yes |
| `server_error` (5xx) | ✅ Yes | ✅ Yes |
| `client_error` (4xx) | ❌ No | ❌ No |
| `timeout` | ❌ No | ✅ Yes |
| `network_error` | ❌ No | ✅ Yes |

---

## Unit 1E: Usage Metering & Observability

### UsageRecorder Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `record_request` | `RequestLog` | `None` | Always record request outcome (Plan/Bedrock) |
| `record_tokens` | `TokenUsageRecord` | `None` | Record Bedrock token usage only |
| `record_async` | `RequestLog`, `TokenUsageRecord?` | `None` | Non-blocking combined record |

### Request Log (Always Recorded)

```python
@dataclass
class RequestLog:
    """Always recorded for every request - Plan and Bedrock."""
    request_id: str
    timestamp: datetime
    user_id: str
    access_key_id: str
    provider: str  # "plan" | "bedrock"
    is_fallback: bool
    status_code: int
    error_type: str | None  # PlanErrorType or BedrockErrorType value
    latency_ms: int
    model: str
```

### Token Usage Record (Bedrock Only)

```python
@dataclass
class TokenUsageRecord:
    """Only recorded for successful Bedrock requests."""
    request_id: str
    timestamp: datetime
    user_id: str
    access_key_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int | None
    cache_creation_input_tokens: int | None
    total_tokens: int
```

### MetricsEmitter Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `emit_latency` | `provider`, `latency_ms` | `None` | Emit latency metric |
| `emit_fallback` | `access_key_id` | `None` | Emit fallback event |
| `emit_error` | `error_type` | `None` | Emit error metric |
| `emit_circuit_state` | `access_key_id`, `state` | `None` | Emit circuit state |
| `emit_provider_request` | `provider`, `success` | `None` | Emit request count by provider |

---

## Unit 2: Admin Backend

### UserService Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `create_user` | `CreateUserRequest` | `User` | Create new user |
| `get_user` | `user_id` | `User \| None` | Get user by ID |
| `list_users` | `filters` | `list[User]` | List users with filters |
| `deactivate_user` | `user_id` | `User` | Deactivate user |

### AccessKeyService Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `issue_key` | `user_id` | `AccessKeyWithSecret` | Issue new key (returns full key once) |
| `revoke_key` | `access_key_id` | `AccessKey` | Revoke key |
| `rotate_key` | `access_key_id` | `AccessKeyWithSecret` | Rotate key |
| `list_keys` | `user_id` | `list[AccessKey]` | List keys for user |

### BedrockKeyService Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `register_key` | `access_key_id`, `bedrock_key` | `None` | Register Bedrock key |
| `rotate_key` | `access_key_id`, `new_key` | `None` | Rotate Bedrock key |
| `has_key` | `access_key_id` | `bool` | Check if key exists |

### UsageService Methods

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `query_usage` | `UsageQuery` | `UsageResult` | Query usage data |
| `get_aggregated` | `user_id`, `bucket`, `range` | `list[UsageAggregate]` | Get aggregated usage |

---

## Repositories (Shared)

### UserRepository

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `create` | `User` | `User` | Insert user |
| `get_by_id` | `user_id` | `User \| None` | Get by ID |
| `list` | `filters` | `list[User]` | List with filters |
| `update` | `User` | `User` | Update user |

### AccessKeyRepository

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `create` | `AccessKey` | `AccessKey` | Insert key |
| `get_by_hash` | `key_hash` | `AccessKey \| None` | Get by HMAC hash |
| `get_by_id` | `access_key_id` | `AccessKey \| None` | Get by ID |
| `list_by_user` | `user_id` | `list[AccessKey]` | List user's keys |
| `update_status` | `access_key_id`, `status` | `AccessKey` | Update status |

### BedrockKeyRepository

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `upsert` | `access_key_id`, `encrypted_key`, `hash`, `prefix` | `None` | Insert or update |
| `get` | `access_key_id` | `BedrockKey \| None` | Get encrypted key |
| `delete` | `access_key_id` | `None` | Delete key |

### RequestLogRepository

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `insert` | `RequestLog` | `None` | Insert request log |
| `query` | `RequestLogQuery` | `list[RequestLog]` | Query logs |
| `get_fallback_rate` | `time_range` | `FallbackStats` | Get fallback statistics |

### TokenUsageRepository

| Method | Input | Output | Description |
|--------|-------|--------|-------------|
| `insert` | `TokenUsageRecord` | `None` | Insert Bedrock token usage |
| `query` | `UsageQuery` | `list[TokenUsageRecord]` | Query records |
| `get_aggregated` | `AggregateQuery` | `list[UsageAggregate]` | Get aggregations |

---

## Key Security Components

### KeyHasher (HMAC-Based)

```python
class KeyHasher:
    """HMAC-based key hashing - NOT plain SHA-256."""
    
    def __init__(self, server_secret: str):
        """
        server_secret: Loaded from AWS Secrets Manager
        NEVER hardcoded in code
        """
        self._secret = server_secret.encode()
    
    def hash(self, raw_key: str) -> str:
        """
        Generate HMAC-SHA256 hash of the key.
        hash = HMAC-SHA256(server_secret, raw_key)
        """
        return hmac.new(
            self._secret,
            raw_key.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def verify(self, raw_key: str, stored_hash: str) -> bool:
        """Constant-time comparison to prevent timing attacks."""
        computed = self.hash(raw_key)
        return hmac.compare_digest(computed, stored_hash)
```

### BedrockKeyCache (TTL Cache for Decrypted Keys)

```python
class BedrockKeyCache:
    """
    In-memory cache for decrypted Bedrock API keys.
    Prevents KMS decrypt call on every request.
    """
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minute default
        self._cache: dict[str, CacheEntry] = {}
        self._ttl = ttl_seconds
    
    def get(self, access_key_id: str) -> str | None:
        """Get cached decrypted key if not expired."""
        entry = self._cache.get(access_key_id)
        if entry and not entry.is_expired():
            return entry.value
        return None
    
    def set(self, access_key_id: str, decrypted_key: str) -> None:
        """Cache decrypted key with TTL."""
        self._cache[access_key_id] = CacheEntry(
            value=decrypted_key,
            expires_at=datetime.utcnow() + timedelta(seconds=self._ttl)
        )
    
    def invalidate(self, access_key_id: str) -> None:
        """Invalidate cache entry - called on rotate/revoke."""
        self._cache.pop(access_key_id, None)
    
    def invalidate_all(self) -> None:
        """Clear entire cache."""
        self._cache.clear()
```

### Key Masking Utility

```python
class KeyMasker:
    """Utility for masking keys in logs and UI."""
    
    @staticmethod
    def mask_access_key(key: str) -> str:
        """
        Access Key: Show ak_ + first 6 chars + ...
        Example: ak_6D3h3X...
        """
        if len(key) > 9:  # ak_ + 6 chars
            return key[:9] + "..."
        return key[:3] + "***"
    
    @staticmethod
    def mask_bedrock_key_for_display() -> str:
        """
        Bedrock Key: Never show any portion.
        Return status only.
        """
        return "●●●●●●●● (Registered)"
    
    @staticmethod
    def mask_for_logging(text: str) -> str:
        """
        Mask any ak_* or bearer tokens in log strings.
        """
        import re
        # Mask access keys
        text = re.sub(r'ak_[A-Za-z0-9_-]+', 'ak_***MASKED***', text)
        # Mask bearer tokens
        text = re.sub(r'Bearer\s+[A-Za-z0-9_-]+', 'Bearer ***MASKED***', text)
        return text
```
