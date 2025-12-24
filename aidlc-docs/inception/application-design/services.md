# Services - ClaudeCodeProxy

## Service Layer Overview

The service layer orchestrates component interactions and provides high-level business operations.

---

## Proxy Service Layer

### ProxyService

**Purpose**: Main entry point for proxy requests, orchestrates the request flow.

**Responsibilities**:
- Receive authenticated request context from Ingress
- Delegate to Router for execution path decision
- Trigger usage recording after response
- Return final response to client

**Orchestration Flow**:
```
HTTP Request
    ↓
IngressHandler (1A)
    ↓ RequestContext
ProxyService
    ↓
Router (1D)
    ↓ calls
PlanAdapter (1B) or BedrockAdapter (1C)
    ↓ response
UsageRecorder (1E)
    ↓
HTTP Response
```

**Key Method**:
```python
class ProxyService:
    def __init__(
        self,
        router: Router,
        usage_recorder: UsageRecorder,
        metrics: MetricsEmitter
    ):
        ...
    
    async def handle_request(
        self,
        ctx: RequestContext,
        request: AnthropicRequest
    ) -> ProxyResponse:
        start_time = time.monotonic()
        
        # Route request
        response = await self.router.route(ctx, request)
        
        # Calculate latency
        latency_ms = int((time.monotonic() - start_time) * 1000)
        
        # Always record request log (Plan and Bedrock)
        request_log = RequestLog(
            request_id=ctx.request_id,
            timestamp=ctx.received_at,
            user_id=ctx.user_id,
            access_key_id=ctx.access_key_id,
            provider=response.provider,
            is_fallback=response.is_fallback,
            status_code=response.status_code,
            error_type=response.error_type,
            latency_ms=latency_ms,
            model=request.model
        )
        
        # Record token usage ONLY for successful Bedrock requests
        token_record = None
        if response.is_success and response.provider == "bedrock":
            token_record = TokenUsageRecord(
                request_id=ctx.request_id,
                timestamp=ctx.received_at,
                user_id=ctx.user_id,
                access_key_id=ctx.access_key_id,
                model=response.response.model,
                input_tokens=response.response.usage.input_tokens,
                output_tokens=response.response.usage.output_tokens,
                cache_read_input_tokens=response.response.usage.cache_read_input_tokens,
                cache_creation_input_tokens=response.response.usage.cache_creation_input_tokens,
                total_tokens=(
                    response.response.usage.input_tokens + 
                    response.response.usage.output_tokens
                )
            )
        
        # Record async (non-blocking)
        await self.usage_recorder.record_async(request_log, token_record)
        
        # Emit metrics
        self.metrics.emit_latency(response.provider, latency_ms)
        self.metrics.emit_provider_request(response.provider, response.is_success)
        if response.is_fallback:
            self.metrics.emit_fallback(ctx.access_key_id)
        if response.error_type:
            self.metrics.emit_error(response.error_type)
        
        return response
```

---

## Admin Service Layer

### UserService

**Purpose**: Manage user lifecycle operations.

**Dependencies**:
- `UserRepository`
- `AccessKeyService` (for cascading operations)

**Key Methods**:
```python
class UserService:
    async def create_user(self, request: CreateUserRequest) -> User:
        user = User(
            id=generate_uuid(),
            name=request.name,
            description=request.description,
            status="active",
            created_at=datetime.utcnow()
        )
        return await self.user_repo.create(user)
    
    async def deactivate_user(self, user_id: str) -> User:
        # Deactivate user
        user = await self.user_repo.update_status(user_id, "inactive")
        # Revoke all access keys
        await self.access_key_service.revoke_all_for_user(user_id)
        return user
```

---

### AccessKeyService

**Purpose**: Manage Access Key lifecycle.

**Dependencies**:
- `AccessKeyRepository`
- `BedrockKeyService`
- `KeyGenerator`
- `KeyHasher` (HMAC-based)
- `AccessKeyCache` (for invalidation on revoke/rotate)

**Key Methods**:
```python
class AccessKeyService:
    async def issue_key(self, user_id: str) -> AccessKeyWithSecret:
        # Generate key
        raw_key = self.key_generator.generate()  # ak_...
        key_hash = self.hasher.hash(raw_key)  # HMAC-SHA256
        key_prefix = raw_key[:9]  # ak_ + 6 chars
        
        access_key = AccessKey(
            id=generate_uuid(),
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            status="active",
            bedrock_region="ap-northeast-2",
            bedrock_model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            created_at=datetime.utcnow()
        )
        await self.access_key_repo.create(access_key)
        
        # Return with secret (only time full key is exposed)
        return AccessKeyWithSecret(
            access_key=access_key,
            secret=raw_key
        )
    
    async def revoke_key(self, access_key_id: str) -> AccessKey:
        key = await self.access_key_repo.update_status(access_key_id, "revoked")
        # Invalidate caches
        self.access_key_cache.invalidate_by_id(access_key_id)
        await self.bedrock_key_service.revoke_key(access_key_id)
        return key
    
    async def rotate_key(self, access_key_id: str) -> AccessKeyWithSecret:
        old_key = await self.access_key_repo.get_by_id(access_key_id)
        
        # Check if has Bedrock key to transfer
        bedrock_key = None
        if await self.bedrock_key_service.has_key(access_key_id):
            bedrock_key = await self.bedrock_key_service.get_decrypted(access_key_id)
        
        # Revoke old key
        await self.revoke_key(access_key_id)
        
        # Issue new key for same user
        new_key = await self.issue_key(old_key.user_id)
        
        # Transfer Bedrock key if existed
        if bedrock_key:
            await self.bedrock_key_service.register_key(new_key.access_key.id, bedrock_key)
        
        return new_key
```

---

### BedrockKeyService

**Purpose**: Manage Bedrock API Key storage with encryption and caching.

**Dependencies**:
- `BedrockKeyRepository`
- `BedrockKeyCache` (TTL cache for decrypted keys)
- `KMSClient` (for envelope encryption)
- `KeyHasher` (HMAC-based)

**Key Methods**:
```python
class BedrockKeyService:
    def __init__(
        self,
        repo: BedrockKeyRepository,
        kms: KMSClient,
        hasher: KeyHasher,
        cache: BedrockKeyCache  # TTL cache for decrypted keys
    ):
        self._repo = repo
        self._kms = kms
        self._hasher = hasher
        self._cache = cache
    
    async def register_key(self, access_key_id: str, bedrock_key: str) -> None:
        # Encrypt with KMS
        encrypted = await self._kms.encrypt(bedrock_key)
        key_hash = self._hasher.hash(bedrock_key)
        
        await self._repo.upsert(
            access_key_id=access_key_id,
            encrypted_key=encrypted,
            key_hash=key_hash,
            key_prefix=""  # Don't store prefix for Bedrock keys
        )
        
        # Invalidate cache for this key
        self._cache.invalidate(access_key_id)
    
    async def rotate_key(self, access_key_id: str, new_key: str) -> None:
        # Same as register - upsert handles replacement
        await self.register_key(access_key_id, new_key)
    
    async def get_decrypted(self, access_key_id: str) -> str | None:
        # Check cache first
        cached = self._cache.get(access_key_id)
        if cached:
            return cached
        
        # Cache miss - fetch and decrypt
        record = await self._repo.get(access_key_id)
        if not record:
            return None
        
        decrypted = await self._kms.decrypt(record.encrypted_key)
        
        # Cache for future requests
        self._cache.set(access_key_id, decrypted)
        
        return decrypted
    
    async def revoke_key(self, access_key_id: str) -> None:
        await self._repo.delete(access_key_id)
        # Invalidate cache
        self._cache.invalidate(access_key_id)
    
    async def has_key(self, access_key_id: str) -> bool:
        record = await self._repo.get(access_key_id)
        return record is not None
```

---

### UsageService

**Purpose**: Query and aggregate usage data.

**Dependencies**:
- `UsageRepository`

**Key Methods**:
```python
class UsageService:
    async def query_usage(self, query: UsageQuery) -> UsageResult:
        # Query based on filters
        if query.bucket:
            # Return aggregated data
            return await self.usage_repo.get_aggregated(
                user_id=query.user_id,
                access_key_id=query.access_key_id,
                bucket=query.bucket,
                start_time=query.start_time,
                end_time=query.end_time
            )
        else:
            # Return raw records
            return await self.usage_repo.query(query)
```

---

### AuthService

**Purpose**: Handle admin authentication.

**Dependencies**:
- `SecretsManager` (for production credentials)
- `SessionStore`

**Key Methods**:
```python
class AuthService:
    async def authenticate(self, username: str, password: str) -> AuthResult:
        # Get credentials based on environment
        if self.is_development:
            valid = username == "admin" and password == "admin"
        else:
            creds = await self.secrets.get_admin_credentials()
            valid = username == creds.username and verify_password(password, creds.password_hash)
        
        if valid:
            token = generate_session_token()
            await self.session_store.create(token, username)
            return AuthResult(success=True, token=token)
        
        return AuthResult(success=False)
```

---

## Service Dependencies Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      PROXY SERVICES                          │
│              (Orchestration Layer - not a unit)              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ProxyService (orchestration)                                │
│      │                                                       │
│      ├── Router (1D)                                         │
│      │      ├── PlanAdapter (1B)                             │
│      │      │      └── HTTP Client                           │
│      │      └── BedrockAdapter (1C)                          │
│      │             └── BedrockKeyService                     │
│      │                    ├── BedrockKeyCache (TTL)          │
│      │                    └── KMSClient                      │
│      │                                                       │
│      ├── UsageRecorder (1E)                                  │
│      │      ├── RequestLogRepository                         │
│      │      └── TokenUsageRepository                         │
│      │                                                       │
│      └── MetricsEmitter (1E)                                 │
│             └── CloudWatchClient                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      ADMIN SERVICES                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  UserService                                                 │
│      ├── UserRepository                                      │
│      └── AccessKeyService                                    │
│                                                              │
│  AccessKeyService                                            │
│      ├── AccessKeyRepository                                 │
│      ├── BedrockKeyService                                   │
│      ├── KeyGenerator                                        │
│      ├── KeyHasher (HMAC-based)                              │
│      └── AccessKeyCache                                      │
│                                                              │
│  BedrockKeyService                                           │
│      ├── BedrockKeyRepository                                │
│      ├── BedrockKeyCache (TTL: 300s)                         │
│      ├── KMSClient                                           │
│      └── KeyHasher (HMAC-based)                              │
│                                                              │
│  UsageService                                                │
│      ├── RequestLogRepository                                │
│      └── TokenUsageRepository                                │
│                                                              │
│  AuthService                                                 │
│      ├── SecretsManager                                      │
│      └── SessionStore                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      SHARED LAYER                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Repositories (Database Access)                              │
│      ├── UserRepository                                      │
│      ├── AccessKeyRepository                                 │
│      ├── BedrockKeyRepository                                │
│      ├── RequestLogRepository                                │
│      └── TokenUsageRepository                                │
│                                                              │
│  Caches                                                      │
│      ├── AccessKeyCache (TTL: 60s)                           │
│      └── BedrockKeyCache (TTL: 300s)                         │
│                                                              │
│  External Clients                                            │
│      ├── KMSClient                                           │
│      ├── SecretsManagerClient                                │
│      └── CloudWatchClient                                    │
│                                                              │
│  Security Utilities                                          │
│      ├── KeyGenerator                                        │
│      ├── KeyHasher (HMAC-SHA256)                             │
│      └── KeyMasker                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Note**: ProxyService is an orchestration layer, not a unit. It coordinates Units 1A-1E but is not independently testable as a unit.
