---
inclusion: always
---

# Product Overview

Claude Code Proxy routes requests from Claude Code to AI providers with automatic failover, usage tracking, and multi-tenant access management.

## Core Capabilities

| Feature | Description |
|---------|-------------|
| Automatic Failover | Routes to Anthropic Plan API; falls back to Amazon Bedrock on rate limits/failures |
| Usage Tracking | Per-user/key token metrics with time-bucketed aggregation |
| Admin Dashboard | Web UI for user/key management, Bedrock credential registration, usage analytics |
| Multi-tenant Access | Unique access keys per user with optional per-key Bedrock credentials |

## User Flows

- **End Users**: Configure `ANTHROPIC_BASE_URL` to proxy endpoint with access key, use Claude Code transparently
- **Admins**: Authenticate via dashboard, manage users/keys, monitor organization-wide usage

## API Contract

### Primary Endpoint

```
POST /ak/{access_key}/v1/messages
```

### Design Constraints

When implementing or modifying proxy behavior:

- Access key MUST be embedded in URL path (`/ak/{access_key}/...`)
- Request/response MUST be fully compatible with Anthropic Messages API schema
- Passthrough headers: `x-api-key`, `authorization`, `anthropic-version`, `anthropic-beta`, `content-type`
- MUST support both streaming and non-streaming responses
- Response format MUST match standard Anthropic format

### Circuit Breaker Rules

| Aspect | Specification |
|--------|---------------|
| Scope | Per-access-key (independent state) |
| Triggers | 429 (rate limit), 500-504 (server errors), connection failures |
| Threshold | 3 failures within 60s window (configurable) |
| Recovery | Auto-closes after 30 minutes (configurable) |
| Half-open | Periodically retries primary after timeout |

### Fallback Behavior

**DO trigger fallback for:**
- `429` rate limit exceeded
- `503` service unavailable
- Connection timeouts / network errors

**DO NOT trigger fallback for:**
- `400` invalid request (user error)
- `401`/`403` authentication failures
- Other `4xx` client errors

## Data Model

### Entity Hierarchy

```
User (admin accounts)
  └─ AccessKey[] (user API keys)
       ├─ BedrockKey (optional, 1:1)
       └─ TokenUsage[] (usage events)
            └─ UsageAggregate[] (time-bucketed stats)
```

### Data Handling Rules

| Pattern | Implementation |
|---------|----------------|
| Soft Delete | Use `deleted_at` timestamp; filter with `deleted_at IS NULL` |
| Bedrock Credentials | KMS envelope encryption at rest |
| Access Keys | HMAC-SHA256 hashed with `PROXY_KEY_HASHER_SECRET` |
| Admin Passwords | SHA256 hashed (legacy; prefer bcrypt/argon2 for new implementations) |

## Cost Model

The proxy enables organizations to:
1. Use Anthropic Plan for normal usage (cost-effective)
2. Auto-fallback to Bedrock PAYG when rate-limited
3. Track usage for cost visibility and capacity planning

### Usage Tracking Fields

- `input_tokens` / `output_tokens`: Per-request token counts
- `provider`: Which backend served the request (plan vs bedrock)
- `is_fallback`: Boolean indicating fallback usage
- `UsageAggregate`: Hourly/daily rollups for analytics
