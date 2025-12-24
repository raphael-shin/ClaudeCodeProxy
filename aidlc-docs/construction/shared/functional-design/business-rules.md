# Business Rules - Shared Foundation

## Access Key Generation

### Rule: AK-GEN-001 - Key Format
```
Format: ak_{random_bytes}
Length: 43-64 characters total
Random: 32+ bytes of cryptographic randomness
Charset: URL-safe Base64 (A-Z, a-z, 0-9, -, _)
```

### Rule: AK-GEN-002 - Key Uniqueness
- Generated key MUST be unique across all keys (active and revoked)
- Collision check via hash lookup before insertion
- Retry generation on collision (max 3 attempts)

### Rule: AK-GEN-003 - Key Display
- Full key shown ONLY once at creation time
- Subsequent displays show: `ak_XXXXXX...` (prefix + 6 chars + ...)
- Never log full key anywhere

---

## Access Key Hashing

### Rule: AK-HASH-001 - HMAC Algorithm
```
Algorithm: HMAC-SHA256
Input: raw_access_key
Key: server_secret (from Secrets Manager)
Output: 64-character hex string
```

### Rule: AK-HASH-002 - Server Secret
- Server secret MUST be loaded from AWS Secrets Manager
- NEVER hardcoded in code or config files
- Rotation: Manual, requires cache invalidation

### Rule: AK-HASH-003 - Verification
- Use constant-time comparison to prevent timing attacks
- `hmac.compare_digest(computed_hash, stored_hash)`

---

## Access Key Validation

### Rule: AK-VAL-001 - Validation Flow
```
1. Check in-memory cache (TTL: 60s)
2. If cache miss: compute hash, query database
3. Validate key status (active or rotating)
4. Validate user status (active)
5. Return RequestContext or None
```

### Rule: AK-VAL-002 - Cache Invalidation
Cache MUST be invalidated on:
- Access Key revoked
- Access Key rotation started
- Access Key rotation completed
- User status changed (deactivated, deleted)

### Rule: AK-VAL-003 - Invalid Key Response
- Return HTTP 404 (not 401) to prevent key enumeration
- Do not reveal whether key exists or is revoked
- Log attempt with masked key for security audit

---

## Access Key Rotation

### Rule: AK-ROT-001 - Grace Period
```
Duration: 5 minutes (configurable)
Old key status: rotating
New key status: active
Both keys valid during grace period
```

### Rule: AK-ROT-002 - Rotation Flow
```
1. Generate new key
2. Set old key status = rotating, rotation_expires_at = now + 5min
3. Insert new key with status = active
4. Transfer Bedrock key association to new key
5. Return new key (full, once only)
6. Background job: revoke old key after grace period
```

### Rule: AK-ROT-003 - Grace Period Expiry
- Background job checks every minute
- Keys with `rotation_expires_at < now` → status = revoked
- Cache invalidation triggered

---

## Bedrock Key Security

### Rule: BK-SEC-001 - Encryption
```
Method: KMS Envelope Encryption
KMS Key: Customer-managed CMK
Storage: encrypted_key column (BYTEA)
```

### Rule: BK-SEC-002 - Decryption Caching
```
Cache: In-memory, per-instance
TTL: 300 seconds (5 minutes)
Invalidation: On rotate, revoke, or access key revoke
```

### Rule: BK-SEC-003 - Display
- NEVER display any portion of Bedrock key
- UI shows only: "Registered" or "Not Registered"
- Logs MUST NOT contain Bedrock key

---

## User Lifecycle

### Rule: USR-LC-001 - Status Transitions
```
Allowed:
  active → inactive (deactivate)
  inactive → deleted (soft delete)

Not Allowed:
  inactive → active (no reactivation)
  deleted → any (terminal state)
```

### Rule: USR-LC-002 - Deactivation Side Effects
When user deactivated:
1. Set user.status = inactive
2. Revoke ALL access keys for user
3. Invalidate ALL cache entries for user's keys
4. Log deactivation event

### Rule: USR-LC-003 - Soft Delete
When user deleted:
1. Set user.status = deleted
2. Set user.deleted_at = now
3. Revoke ALL access keys (if not already)
4. Retain data for audit (no physical delete)

---

## Request Logging & Usage Recording

### Rule: LOG-001 - CloudWatch Structured Logging
모든 요청 완료 시 CloudWatch Logs에 structured log 기록:
```json
{
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

### Rule: LOG-002 - Token Usage (DB 저장)
Token usage는 DB에 저장 (Bedrock 성공 요청만):
- `token_usage` 테이블이 유일한 DB 요청 데이터
- Plan 요청은 DB에 저장하지 않음 (CloudWatch Logs만)
- 실패 요청은 DB에 저장하지 않음 (CloudWatch Logs만)

저장 필드:
- request_id, timestamp, user_id, access_key_id
- model, input_tokens, output_tokens, total_tokens
- cache_read_input_tokens, cache_creation_input_tokens
- provider (항상 'bedrock'), is_fallback, latency_ms

### Rule: LOG-003 - Log Masking
Logs MUST NOT contain:
- Full access keys (use prefix only)
- Bedrock API keys
- Request/response bodies
- User PII beyond user_id

### Rule: LOG-004 - 요청 추적
요청 단위 디버깅은 CloudWatch Logs Insights에서 request_id로 조회:
```sql
fields @timestamp, request_id, provider_used, is_fallback, status_code, latency_ms
| filter request_id = "req_abc123"
```

---

## Error Classification

### Rule: ERR-001 - Plan Error Types
| Error Type | Condition | Triggers Circuit | Allows Fallback |
|------------|-----------|------------------|-----------------|
| rate_limit | HTTP 429 | Yes | Yes |
| usage_limit | Usage exceeded | No | Yes |
| server_error | HTTP 5xx | Yes | Yes |
| client_error | HTTP 4xx (non-429) | No | No |
| timeout | Request timeout | No | Yes |
| network_error | Connection failed | No | Yes |

### Rule: ERR-002 - Bedrock Error Types
| Error Type | Condition |
|------------|-----------|
| bedrock_auth_error | AccessDeniedException |
| bedrock_quota_exceeded | ThrottlingException |
| bedrock_validation | ValidationException |
| bedrock_model_error | ModelError |
| bedrock_unavailable | Other errors, timeout |

### Rule: ERR-003 - Error Response Format
```json
{
  "type": "error",
  "error": {
    "type": "rate_limit_error",
    "message": "Rate limit exceeded"
  },
  "request_id": "req_abc123..."
}
```
- Anthropic-compatible format
- Always include proxy request_id
- Pass through original error details when applicable
