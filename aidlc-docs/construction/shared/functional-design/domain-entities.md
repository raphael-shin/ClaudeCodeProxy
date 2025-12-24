# Domain Entities - Shared Foundation

## Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────┐       ┌──────────────┐
│    User     │──1:N──│  AccessKey   │──1:1──│  BedrockKey  │
└─────────────┘       └──────────────┘       └──────────────┘
       │                     │
       │                     │
       └──────────┬──────────┘
                  │
                  ▼
          ┌──────────────┐
          │  TokenUsage  │
          └──────────────┘
```

**설계 원칙**:
- PostgreSQL에는 Bedrock token_usage만 저장
- 요청 로그/디버깅은 CloudWatch Logs로 해결 (request_id 기반 조회)

---

## User

### Attributes

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique identifier |
| name | VARCHAR(255) | NOT NULL | Display name |
| description | TEXT | NULLABLE | Optional description |
| status | ENUM | NOT NULL | active, inactive, deleted |
| created_at | TIMESTAMPTZ | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL | Last update timestamp |
| deleted_at | TIMESTAMPTZ | NULLABLE | Soft delete timestamp |

### Status State Machine

```
     ┌─────────┐
     │ active  │
     └────┬────┘
          │ deactivate()
          ▼
     ┌─────────┐
     │inactive │
     └────┬────┘
          │ delete()
          ▼
     ┌─────────┐
     │ deleted │ (soft delete)
     └─────────┘
```

### Business Rules
- `active`: User can authenticate, access keys are valid
- `inactive`: User cannot authenticate, all access keys are invalidated
- `deleted`: Soft delete, data retained for audit, all access keys revoked
- No reactivation allowed (one-way transitions)

---

## AccessKey

### Attributes

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique identifier |
| user_id | UUID | FK(User), NOT NULL | Owner user |
| key_hash | VARCHAR(64) | NOT NULL, UNIQUE | HMAC-SHA256 hash |
| key_prefix | VARCHAR(12) | NOT NULL | Display prefix (ak_ + 6 chars) |
| status | ENUM | NOT NULL | active, revoked, rotating |
| bedrock_region | VARCHAR(32) | NOT NULL | Default: ap-northeast-2 |
| bedrock_model | VARCHAR(128) | NOT NULL | Default model ID |
| created_at | TIMESTAMPTZ | NOT NULL | Creation timestamp |
| revoked_at | TIMESTAMPTZ | NULLABLE | Revocation timestamp |
| rotation_expires_at | TIMESTAMPTZ | NULLABLE | Grace period expiry |

### Status State Machine

```
     ┌─────────┐
     │ active  │◄─────────────┐
     └────┬────┘              │
          │                   │
    ┌─────┴─────┐             │
    │           │             │
    ▼           ▼             │
┌───────┐  ┌──────────┐       │
│revoked│  │ rotating │───────┘
└───────┘  └──────────┘  (grace period expires,
                          new key confirmed)
```

### Business Rules
- `active`: Key can be used for authentication
- `rotating`: Grace period active, both old and new keys valid
- `revoked`: Key permanently invalid
- Grace period: 5 minutes (configurable)
- When user deactivated → all keys revoked

---

## BedrockKey

### Attributes

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| access_key_id | UUID | PK, FK(AccessKey) | 1:1 with AccessKey |
| encrypted_key | BYTEA | NOT NULL | KMS envelope encrypted |
| key_hash | VARCHAR(64) | NOT NULL | HMAC-SHA256 for validation |
| created_at | TIMESTAMPTZ | NOT NULL | Registration timestamp |
| rotated_at | TIMESTAMPTZ | NULLABLE | Last rotation timestamp |

### Business Rules
- 1:1 relationship with AccessKey
- Never stored in plaintext
- Never displayed after registration
- Deleted when AccessKey revoked

---

## TokenUsage

**단일 소스**: DB에 저장되는 유일한 요청 관련 데이터. Bedrock 성공 요청만 기록.

### Attributes

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique identifier |
| request_id | VARCHAR(64) | NOT NULL, UNIQUE | Trace ID (로그 상관관계) |
| timestamp | TIMESTAMPTZ | NOT NULL | Usage timestamp |
| user_id | UUID | NOT NULL | User reference |
| access_key_id | UUID | NOT NULL | Key used |
| model | VARCHAR(128) | NOT NULL | Model used |
| input_tokens | INTEGER | NOT NULL | Input token count |
| output_tokens | INTEGER | NOT NULL | Output token count |
| cache_read_input_tokens | INTEGER | NULLABLE | Cache read tokens |
| cache_creation_input_tokens | INTEGER | NULLABLE | Cache creation tokens |
| total_tokens | INTEGER | NOT NULL | Computed total |
| provider | VARCHAR(10) | NOT NULL, DEFAULT 'bedrock' | 항상 bedrock |
| is_fallback | BOOLEAN | NOT NULL | Plan 실패 후 Bedrock 사용 여부 |
| latency_ms | INTEGER | NOT NULL | Bedrock 요청 지연시간 |

### Indexes
- `UNIQUE(request_id)` - Bedrock 호출 1회 가정
- `(timestamp)` - 시간 범위 조회
- `(user_id, timestamp)` - 사용자별 조회
- `(access_key_id, timestamp)` - 키별 조회

### Business Rules
- Only recorded for successful Bedrock requests
- Plan usage NOT recorded (tracked by Claude Code plans)
- Immutable after creation
- Used for aggregation and dashboard
- `is_fallback=true`: Plan 실패 후 Bedrock으로 전환된 요청

---

## UsageAggregate

### Attributes

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | PK, NOT NULL | Unique identifier |
| bucket_type | ENUM | NOT NULL | minute, hour, day, month |
| bucket_start | TIMESTAMPTZ | NOT NULL | Bucket start time |
| user_id | UUID | NOT NULL | User reference |
| access_key_id | UUID | NULLABLE | Optional key filter |
| total_requests | INTEGER | NOT NULL | Request count (= token_usage row count) |
| total_input_tokens | BIGINT | NOT NULL | Sum of input tokens |
| total_output_tokens | BIGINT | NOT NULL | Sum of output tokens |
| total_tokens | BIGINT | NOT NULL | Sum of all tokens |

### Business Rules
- Pre-aggregated for dashboard performance
- `total_requests` = Bedrock 사용 횟수 (token_usage row count)
- Minute buckets: retain 14 days
- Hour/day/month buckets: retain indefinitely
- Updated by background job or trigger
