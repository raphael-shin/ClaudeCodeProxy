# NFR Design Patterns - ClaudeCodeProxy

## Resilience Patterns

### Circuit Breaker Pattern

**Purpose**: Prevent cascade failures when Plan upstream is unavailable.

**Implementation**:
```
State: CLOSED → OPEN → HALF_OPEN → CLOSED
Trigger: 3 consecutive failures (429/5xx) in 1 minute
Reset: 30 minutes
Scope: Per Access Key (in-memory)
```

**Design**:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, failure_window=60, reset_timeout=1800):
        self._states: dict[str, CircuitState] = {}
    
    def is_open(self, key_id: str) -> bool:
        state = self._states.get(key_id)
        if not state:
            return False
        if state.state == "OPEN" and self._should_half_open(state):
            state.state = "HALF_OPEN"
            return False
        return state.state == "OPEN"
    
    def record_failure(self, key_id: str) -> None:
        # Only called for rate_limit or server_error
        state = self._get_or_create(key_id)
        state.failure_count += 1
        state.last_failure_at = datetime.utcnow()
        if state.failure_count >= self._threshold:
            state.state = "OPEN"
            state.opened_at = datetime.utcnow()
```

---

### Retry with Fallback Pattern

**Purpose**: Automatically retry failed Plan requests with Bedrock.

**Implementation**:
```
1. Try Plan upstream
2. On retryable error (429, 5xx, timeout):
   - If has_bedrock_key: Try Bedrock
   - Else: Return 503
3. On non-retryable error: Return error
```

**Design**:
```python
async def route(self, ctx: RequestContext, request: AnthropicRequest) -> ProxyResponse:
    # Try Plan first (unless circuit open)
    if not self.circuit.is_open(ctx.access_key_id):
        result = await self.plan_adapter.invoke(ctx, request)
        if isinstance(result, AdapterResponse):
            return ProxyResponse.success(result, provider="plan")
        
        # Record failure for circuit breaker
        if result.error_type in CIRCUIT_TRIGGERS:
            self.circuit.record_failure(ctx.access_key_id)
        
        # Fallback to Bedrock if retryable
        if result.retryable and ctx.has_bedrock_key:
            return await self._try_bedrock(ctx, request)
    
    # Circuit open - go direct to Bedrock
    if ctx.has_bedrock_key:
        return await self._try_bedrock(ctx, request)
    
    return ProxyResponse.error(503, "Service unavailable")
```

---

### Timeout Pattern

**Purpose**: Prevent hanging requests from consuming resources.

**Configuration**:
```python
TIMEOUTS = {
    "connect": 5.0,      # Connection establishment
    "read": 300.0,       # Response read (5 min for long completions)
    "write": 30.0,       # Request write
    "pool": 10.0         # Connection pool acquisition
}
```

---

## Performance Patterns

### Connection Pooling

**Purpose**: Reuse database and HTTP connections for efficiency.

**Database Pool**:
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True
)
```

**HTTP Client Pool**:
```python
# Shared httpx client with connection pooling
http_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
        keepalive_expiry=30
    ),
    timeout=httpx.Timeout(
        connect=5.0,
        read=300.0,
        write=30.0,
        pool=10.0
    )
)
```

---

### Caching Pattern

**Purpose**: Reduce database and KMS calls for frequently accessed data.

**Access Key Cache**:
```python
class AccessKeyCache:
    TTL = 60  # seconds
    
    def get(self, key_hash: str) -> RequestContext | None:
        entry = self._cache.get(key_hash)
        if entry and not entry.is_expired():
            return entry.value
        return None
    
    def set(self, key_hash: str, context: RequestContext) -> None:
        self._cache[key_hash] = CacheEntry(context, expires_at=now() + TTL)
    
    def invalidate(self, key_hash: str) -> None:
        self._cache.pop(key_hash, None)
```

**Bedrock Key Cache**:
```python
class BedrockKeyCache:
    TTL = 300  # 5 minutes (reduce KMS calls)
    
    # Same pattern as AccessKeyCache
    # Invalidated on key rotate/revoke
```

---

### Async I/O Pattern

**Purpose**: Non-blocking operations for high concurrency.

**Implementation**:
```python
# All I/O operations are async
async def handle_request(ctx: RequestContext, request: AnthropicRequest):
    # Parallel operations where possible
    async with asyncio.TaskGroup() as tg:
        response_task = tg.create_task(route_request(ctx, request))
    
    response = response_task.result()
    
    # Non-blocking logging (fire and forget)
    asyncio.create_task(record_usage(ctx, response))
    
    return response
```

---

## Security Patterns

### Envelope Encryption Pattern

**Purpose**: Secure storage of Bedrock API keys.

**Implementation**:
```
1. Generate data key from KMS CMK
2. Encrypt Bedrock key with data key
3. Store: encrypted_data_key + encrypted_bedrock_key
4. Decrypt: KMS decrypt data key → decrypt Bedrock key
```

**Design**:
```python
class KMSEnvelopeEncryption:
    async def encrypt(self, plaintext: str) -> bytes:
        # Generate data key
        response = await self.kms.generate_data_key(
            KeyId=self.cmk_id,
            KeySpec='AES_256'
        )
        data_key = response['Plaintext']
        encrypted_data_key = response['CiphertextBlob']
        
        # Encrypt with data key
        cipher = AES.new(data_key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())
        
        # Return combined blob
        return encrypted_data_key + cipher.nonce + tag + ciphertext
    
    async def decrypt(self, blob: bytes) -> str:
        # Parse blob
        encrypted_data_key = blob[:256]
        nonce = blob[256:268]
        tag = blob[268:284]
        ciphertext = blob[284:]
        
        # Decrypt data key with KMS
        response = await self.kms.decrypt(CiphertextBlob=encrypted_data_key)
        data_key = response['Plaintext']
        
        # Decrypt with data key
        cipher = AES.new(data_key, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        
        return plaintext.decode()
```

---

### HMAC Authentication Pattern

**Purpose**: Secure Access Key validation without storing plaintext.

**Implementation**:
```python
class KeyHasher:
    def __init__(self, server_secret: str):
        self._secret = server_secret.encode()
    
    def hash(self, raw_key: str) -> str:
        return hmac.new(
            self._secret,
            raw_key.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def verify(self, raw_key: str, stored_hash: str) -> bool:
        computed = self.hash(raw_key)
        return hmac.compare_digest(computed, stored_hash)
```

---

### Request Masking Pattern

**Purpose**: Prevent sensitive data in logs.

**Implementation**:
```python
class LogMasker:
    PATTERNS = [
        (r'ak_[A-Za-z0-9_-]+', 'ak_***'),
        (r'Bearer\s+[A-Za-z0-9_-]+', 'Bearer ***'),
    ]
    
    @classmethod
    def mask(cls, text: str) -> str:
        for pattern, replacement in cls.PATTERNS:
            text = re.sub(pattern, replacement, text)
        return text
```

---

## Scalability Patterns

### Horizontal Scaling

**Purpose**: Handle increased load by adding instances.

**ECS Auto-Scaling**:
```python
# CDK configuration
scaling = service.auto_scale_task_count(
    min_capacity=2,
    max_capacity=10
)

scaling.scale_on_cpu_utilization(
    "CpuScaling",
    target_utilization_percent=70,
    scale_in_cooldown=Duration.seconds(300),
    scale_out_cooldown=Duration.seconds(60)
)

scaling.scale_on_memory_utilization(
    "MemoryScaling",
    target_utilization_percent=80,
    scale_in_cooldown=Duration.seconds(300),
    scale_out_cooldown=Duration.seconds(60)
)
```

---

### Database Scaling

**Purpose**: Handle database load growth.

**Aurora Serverless v2**:
```python
# Auto-scales between 0.5 and 4 ACU
# No manual intervention needed
# Read replicas can be added if needed
```

---

## Observability Patterns

### Structured Logging

**Purpose**: Machine-parseable logs for analysis. DB에 request_logs 없이 CloudWatch가 요청 추적의 단일 소스.

**필수 필드** (모든 요청 완료 로그):
```python
import structlog

logger = structlog.get_logger()

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

# 요청 완료 시 필수 로깅
logger.info(
    "request_completed",
    request_id=ctx.request_id,
    access_key_prefix=ctx.access_key_prefix,
    provider_attempted=["plan", "bedrock"],  # 시도한 순서
    provider_used=response.provider,          # 최종 사용
    is_fallback=response.is_fallback,
    status_code=response.status_code,
    error_type=response.error_type,           # None if success
    latency_ms=latency,
    model=request.model
)
```

**Output**:
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "level": "info",
  "event": "request_completed",
  "request_id": "req_abc123",
  "access_key_prefix": "ak_abc12345",
  "provider_attempted": ["plan", "bedrock"],
  "provider_used": "bedrock",
  "is_fallback": true,
  "status_code": 200,
  "error_type": null,
  "latency_ms": 150,
  "model": "claude-sonnet-4-20250514"
}
```

---

### CloudWatch Logs Insights 쿼리 템플릿

**요청 추적 (request_id 기반)**:
```sql
fields @timestamp, request_id, provider_used, is_fallback, status_code, latency_ms
| filter request_id = "req_abc123"
| sort @timestamp desc
```

**키별 Fallback 분석**:
```sql
fields @timestamp, access_key_prefix, is_fallback
| filter is_fallback = true
| stats count() as fallback_count by access_key_prefix
| sort fallback_count desc
```

**에러 분석**:
```sql
fields @timestamp, request_id, error_type, provider_used
| filter error_type != ""
| stats count() as error_count by error_type, provider_used
| sort error_count desc
```

---

### Metrics Emission

**Purpose**: Real-time monitoring and alerting.

**필수 메트릭**:
```python
class MetricsEmitter:
    def __init__(self, cloudwatch: CloudWatchClient):
        self._cw = cloudwatch
        self._namespace = "ClaudeCodeProxy"
    
    async def emit_request(self, provider: str, is_fallback: bool, latency_ms: int):
        await self._cw.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                {"MetricName": "RequestCount", "Value": 1, "Unit": "Count",
                 "Dimensions": [{"Name": "Provider", "Value": provider}]},
                {"MetricName": "RequestLatency", "Value": latency_ms, "Unit": "Milliseconds",
                 "Dimensions": [{"Name": "Provider", "Value": provider}]},
            ]
        )
        if is_fallback:
            await self._cw.put_metric_data(
                Namespace=self._namespace,
                MetricData=[{"MetricName": "FallbackCount", "Value": 1, "Unit": "Count"}]
            )
    
    async def emit_error(self, error_type: str, provider: str):
        await self._cw.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                {"MetricName": "ErrorCount", "Value": 1, "Unit": "Count",
                 "Dimensions": [
                     {"Name": "ErrorType", "Value": error_type},
                     {"Name": "Provider", "Value": provider}
                 ]}
            ]
        )
    
    async def emit_circuit_open(self, access_key_id: str):
        await self._cw.put_metric_data(
            Namespace=self._namespace,
            MetricData=[{"MetricName": "CircuitOpen", "Value": 1, "Unit": "Count"}]
        )
    
    async def emit_tokens(self, input_tokens: int, output_tokens: int):
        await self._cw.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                {"MetricName": "BedrockTokensUsed", "Value": input_tokens, "Unit": "Count",
                 "Dimensions": [{"Name": "TokenType", "Value": "input"}]},
                {"MetricName": "BedrockTokensUsed", "Value": output_tokens, "Unit": "Count",
                 "Dimensions": [{"Name": "TokenType", "Value": "output"}]},
            ]
        )
```

**메트릭 목록**:
| Metric | Dimensions | Unit |
|--------|------------|------|
| RequestCount | Provider (plan/bedrock) | Count |
| RequestLatency | Provider | Milliseconds |
| FallbackCount | - | Count |
| ErrorCount | ErrorType, Provider | Count |
| CircuitOpen | - | Count |
| BedrockTokensUsed | TokenType (input/output) | Count |
