# Business Logic Model - Shared Foundation

## Authentication Flow (Unit 1A)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Authentication Flow                           │
└─────────────────────────────────────────────────────────────────┘

    HTTP Request: POST /ak/{access_key}/v1/messages
                            │
                            ▼
                   ┌────────────────┐
                   │ Extract Key    │
                   │ from URL Path  │
                   └───────┬────────┘
                           │
                           ▼
                   ┌────────────────┐
                   │ Check Cache    │
                   │ (TTL: 60s)     │
                   └───────┬────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
         cache hit                 cache miss
              │                         │
              ▼                         ▼
    ┌─────────────────┐       ┌─────────────────┐
    │ Return Cached   │       │ Compute HMAC    │
    │ RequestContext  │       │ Hash            │
    └─────────────────┘       └────────┬────────┘
                                       │
                                       ▼
                              ┌─────────────────┐
                              │ Query DB by     │
                              │ key_hash        │
                              └────────┬────────┘
                                       │
                          ┌────────────┴────────────┐
                          │                         │
                     not found                    found
                          │                         │
                          ▼                         ▼
                   ┌──────────┐            ┌─────────────────┐
                   │ Return   │            │ Validate Status │
                   │ HTTP 404 │            │ (key + user)    │
                   └──────────┘            └────────┬────────┘
                                                    │
                                       ┌────────────┴────────────┐
                                       │                         │
                                   invalid                     valid
                                       │                         │
                                       ▼                         ▼
                                ┌──────────┐            ┌─────────────────┐
                                │ Return   │            │ Build Context   │
                                │ HTTP 404 │            │ + Cache + Return│
                                └──────────┘            └─────────────────┘
```

### RequestContext Structure
```python
RequestContext:
  request_id: str          # Generated UUID
  user_id: str             # From AccessKey.user_id
  access_key_id: str       # AccessKey.id
  bedrock_region: str      # AccessKey.bedrock_region
  bedrock_model: str       # AccessKey.bedrock_model
  has_bedrock_key: bool    # BedrockKey exists?
  received_at: datetime    # Request received timestamp
```

---

## Routing Flow (Unit 1D)

```
┌─────────────────────────────────────────────────────────────────┐
│                       Routing Flow                               │
└─────────────────────────────────────────────────────────────────┘

    RequestContext + AnthropicRequest
                    │
                    ▼
           ┌────────────────┐
           │ Check Circuit  │
           │ Breaker State  │
           └───────┬────────┘
                   │
      ┌────────────┴────────────┐
      │                         │
   CLOSED                     OPEN
      │                         │
      ▼                         ▼
┌──────────────┐       ┌────────────────────┐
│ Try Plan     │       │ has_bedrock_key?   │
│ Upstream     │       └─────────┬──────────┘
└──────┬───────┘                 │
       │                ┌────────┴────────┐
       │                │                 │
  ┌────┴────┐         Yes                No
  │         │           │                 │
success   error         ▼                 ▼
  │         │    ┌────────────┐    ┌──────────┐
  │         │    │ Try Bedrock│    │ HTTP 503 │
  │         │    │ Direct     │    │ "Circuit │
  │         │    └────────────┘    │  Open"   │
  │         │                      └──────────┘
  │         │
  ▼         ▼
┌─────┐  ┌─────────────────────────────────┐
│Done │  │ Classify Error                  │
└─────┘  └──────────────┬──────────────────┘
                        │
           ┌────────────┴────────────┐
           │                         │
    triggers circuit           doesn't trigger
    (rate_limit, server_error)  (other errors)
           │                         │
           ▼                         │
    ┌──────────────┐                 │
    │ Record       │                 │
    │ Failure      │                 │
    └──────┬───────┘                 │
           │                         │
           └────────────┬────────────┘
                        │
                        ▼
               ┌────────────────────┐
               │ has_bedrock_key?   │
               │ && retryable?      │
               └─────────┬──────────┘
                         │
                ┌────────┴────────┐
                │                 │
              Yes                No
                │                 │
                ▼                 ▼
         ┌────────────┐    ┌──────────┐
         │ Try Bedrock│    │ Return   │
         │ Fallback   │    │ Error    │
         └──────┬─────┘    └──────────┘
                │
           ┌────┴────┐
           │         │
        success    error
           │         │
           ▼         ▼
        ┌─────┐  ┌──────────┐
        │Done │  │ Return   │
        │     │  │ Error    │
        └─────┘  └──────────┘
```

---

## Circuit Breaker State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                  Circuit Breaker States                          │
└─────────────────────────────────────────────────────────────────┘

                    ┌──────────────┐
         ┌─────────│   CLOSED     │◄────────────┐
         │         │ (normal)     │             │
         │         └──────┬───────┘             │
         │                │                     │
         │         3 failures in 1 min          │
         │                │                     │
         │                ▼                     │
         │         ┌──────────────┐             │
         │         │    OPEN      │             │
         │         │ (skip Plan)  │             │
         │         └──────┬───────┘             │
         │                │                     │
         │         30 minutes elapsed           │
         │                │                     │
         │                ▼                     │
         │         ┌──────────────┐             │
         │         │  HALF_OPEN   │─────────────┘
         │         │ (test Plan)  │   success
         │         └──────┬───────┘
         │                │
         │           failure
         │                │
         └────────────────┘
              (back to OPEN)
```

### Circuit Breaker Configuration
```
failure_threshold: 3        # Consecutive failures to open
failure_window: 60          # Seconds to count failures
reset_timeout: 1800         # Seconds before half-open (30 min)
scope: per-access-key       # Each key has own circuit
storage: in-memory          # Per-instance, not shared
```

### Failure Tracking
```python
CircuitState:
  access_key_id: str
  state: CLOSED | OPEN | HALF_OPEN
  failure_count: int
  last_failure_at: datetime
  opened_at: datetime | None
```

---

## Plan Adapter Flow (Unit 1B)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Plan Adapter Flow                             │
└─────────────────────────────────────────────────────────────────┘

    RequestContext + AnthropicRequest
                    │
                    ▼
           ┌────────────────┐
           │ Build HTTP     │
           │ Request        │
           └───────┬────────┘
                   │
                   ▼
           ┌────────────────┐
           │ Add Headers    │
           │ - Authorization│
           │ - anthropic-ver│
           │ - Content-Type │
           └───────┬────────┘
                   │
                   ▼
           ┌────────────────┐
           │ POST to        │
           │ api.anthropic  │
           │ .com/v1/messages
           └───────┬────────┘
                   │
              ┌────┴────┐
              │         │
           success    error
              │         │
              ▼         ▼
    ┌─────────────┐  ┌─────────────────┐
    │ Parse       │  │ Classify Error  │
    │ Response    │  │ (rate_limit,    │
    │ → Adapter   │  │  server_error,  │
    │   Response  │  │  client_error)  │
    └─────────────┘  └─────────────────┘
```

### Request Transformation
```
Input: AnthropicRequest (from Claude Code)
Output: HTTP Request to Anthropic API

Headers:
  Authorization: Bearer {token} (pass-through if provided)
  x-api-key: {api_key} (pass-through if provided)
  anthropic-version: 2023-06-01 (default if missing)
  anthropic-beta: pass-through if provided
  Content-Type: application/json (default if missing)

Body: Pass through AnthropicRequest as-is (exclude internal-only fields like `original_model`)
```

### Response Handling
```
Success (2xx):
  - Parse response body
  - Extract usage metrics
  - Return AdapterResponse

Error (4xx, 5xx):
  - Classify error type
  - Add request_id to error
  - Return AdapterError
```

### Streaming Handling
```
If request.stream is true:
  - Forward request to /v1/messages with stream enabled
  - Do not JSON-parse the body
  - Stream bytes back to client as-is (SSE passthrough)
```

### Count Tokens
```
POST /v1/messages/count_tokens
  - Same header passthrough rules as /v1/messages
  - Return JSON response from Plan upstream
```

---

## Error Response Passthrough

### Rule: Pass Through with Metadata
```
Original Anthropic Error:
{
  "type": "error",
  "error": {
    "type": "rate_limit_error",
    "message": "Rate limit exceeded"
  }
}

Proxy Response (with metadata):
{
  "type": "error",
  "error": {
    "type": "rate_limit_error",
    "message": "Rate limit exceeded"
  },
  "request_id": "req_abc123def456"
}
```

### Passthrough Rules
1. Preserve original error structure
2. Add `request_id` at top level
3. Do not modify `error.type` or `error.message`
4. For proxy-generated errors, use Anthropic-compatible format
