# Product Overview

Claude Code Proxy is a proxy service that sits between Claude Code (Anthropic's coding assistant) and backend AI providers. It provides:

- **Automatic Failover**: Routes requests to Anthropic Plan API, with automatic fallback to Amazon Bedrock Converse when rate-limited or failing
- **Usage Tracking**: Tracks token usage per user/access key with aggregated metrics
- **Admin Dashboard**: Web UI for managing users, issuing access keys, registering Bedrock credentials, and viewing usage analytics
- **Multi-tenant Access**: Each user gets unique access keys with optional per-key Bedrock credentials

## Key User Flows

1. **End Users**: Set `ANTHROPIC_BASE_URL` to proxy endpoint with their access key, use Claude Code normally
2. **Admins**: Login to dashboard, manage users/keys, monitor usage across the organization

## Business Context

- Enables organizations to manage and monitor Claude Code usage centrally
- Provides cost visibility through usage tracking
- Ensures availability via Bedrock fallback when Anthropic API is rate-limited

## API Contract

### Primary Endpoint
```
POST /ak/{access_key}/v1/messages
```

**Key Design Points**:
- Access key is embedded in URL path (`/ak/{access_key}/...`) for transparent routing
- Fully compatible with Anthropic Messages API schema
- Passthrough headers: `x-api-key`, `authorization`, `anthropic-version`, `anthropic-beta`, `content-type`
- Supports both streaming and non-streaming responses
- Returns standard Anthropic response format with added internal tracking

### Circuit Breaker Behavior
- **Per-key state**: Each access key has independent circuit breaker state
- **Trigger conditions**: Opens on rate limits (429), server errors (500-504), or repeated failures
- **Thresholds**: 3 failures within 60s window (configurable)
- **Recovery**: Auto-closes after 30 minutes (configurable)
- **Half-open testing**: Periodically retries after timeout before fully closing

### Fallback Logic
When Anthropic Plan API fails with:
- `429` (rate limit exceeded)
- `503` (service unavailable)
- Connection timeouts or network errors

→ Automatically retries via Amazon Bedrock using registered credentials

**Fallback is NOT triggered for**:
- `400` (invalid request) - user error
- `401`/`403` (authentication) - credential issue
- `4xx` client errors - should not be retried

## Data Model

### Core Entities
```
User (admin accounts)
  └─ AccessKey[] (user API keys)
       ├─ BedrockKey (optional, 1:1 with AccessKey)
       └─ TokenUsage[] (usage events)
            └─ UsageAggregate[] (time-bucketed stats)
```

### Soft Delete Pattern
- Users and access keys use `deleted_at` timestamp (not hard delete)
- Preserves usage history for audit/analytics
- Deleted resources excluded from active queries via filter

### Encryption Model
- **Bedrock credentials**: KMS envelope encryption (encrypted at rest in DB)
- **Access keys**: HMAC-SHA256 hashed with secret salt
- **Admin passwords**: SHA256 hashed (should migrate to bcrypt/argon2)

## Cost Model Context

### Why This Exists
Anthropic Plan ($40/month) has usage limits. Organizations can:
1. Use Plan for normal usage (cost-effective)
2. Auto-fallback to Bedrock PAYG when rate-limited
3. Track actual usage to understand cost implications

### Cost Visibility Features
- Token tracking: input/output tokens per request
- Provider tracking: which backend served the request (plan vs bedrock)
- Fallback tracking: was this a fallback request?
- Aggregation: hourly/daily rollups for analytics
- Top users: identify heavy users for capacity planning
