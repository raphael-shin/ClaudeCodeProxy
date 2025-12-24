# Project Context - ClaudeCodeProxy

Developer and AI-oriented overview of how the proxy works, where to look, and
which files matter most.

## Purpose
- Accept Claude Code compatible requests and proxy to Anthropic Plan.
- Provide automatic Bedrock fallback via Converse when Plan fails.
- Track Bedrock usage and expose an admin dashboard.

Primary docs: `README.md`, `aidlc-docs/`.

## Repository map
```
backend/   FastAPI API + proxy logic + database access
frontend/  Next.js admin UI (App Router)
infra/     AWS CDK stacks (VPC, RDS, ECS, ALB, Secrets, KMS, CloudWatch)
aidlc-docs/ Requirements and design artifacts
```

## Request flow (messages)
1) Client calls `POST /ak/{access_key}/v1/messages`.
2) Access key is HMAC-hashed and looked up, with metadata cached by TTL.
3) Proxy forwards request to Anthropic Plan using the client `x-api-key`.
4) Retryable Plan failures trigger Bedrock fallback when a Bedrock key exists.
5) Bedrock Converse responses are normalized to Anthropic Messages format.
6) Usage is recorded for successful Bedrock responses.

Core entry points:
- `backend/src/api/proxy_router.py`
- `backend/src/proxy/router.py`
- `backend/src/proxy/auth.py`

## Bedrock fallback and normalization
- Adapter: `backend/src/proxy/bedrock_adapter.py`
  - Uses `httpx.AsyncClient`.
  - Calls `.../model/{modelId}/converse` or `/converse-stream`.
  - Auth header: `Authorization: Bearer <bedrock_key>`.
  - Model IDs are normalized by stripping `bedrock/` or `converse/`.
- Normalization + streaming conversion: `backend/src/proxy/bedrock_converse.py`
  - Builds Converse requests from Anthropic Messages payloads.
  - Converts Converse responses back to Anthropic format.
  - Translates event stream chunks into Anthropic SSE events.

## Auth, keys, and caching
- Access key metadata is cached in `backend/src/proxy/auth.py`.
- Request IDs are generated per request (not cached).
- Bedrock keys are encrypted; KMS is used in AWS, local key in dev.
- Registering a Bedrock key invalidates cached access key metadata.

Key files:
- `backend/src/security/keys.py`
- `backend/src/api/admin_keys.py`
- `backend/src/db/models.py`

## Usage tracking and timezones
- Usage is recorded only for successful Bedrock responses.
- Timestamps are stored in UTC via `datetime.utcnow()`.
- Aggregates are updated for minute/hour/day/week/month buckets.
- APIs:
  - `GET /admin/usage` (global totals by default, filter by user/access key)
  - `GET /admin/usage/top-users` (top token consumers)
- The UI formats timestamps client-side; current options include UTC and Asia/Seoul.

Relevant files:
- `backend/src/proxy/usage.py`
- `backend/src/repositories/usage_repository.py`
- `backend/src/api/admin_usage.py`
- `frontend/src/app/usage/page.tsx`
- `frontend/src/lib/api.ts`

## Admin API surface
- Auth: `POST /admin/auth/login` (Basic -> JWT)
- Users: `GET/POST /admin/users`
- Access keys: `POST /admin/users/{id}/access-keys`, `POST /admin/access-keys/{id}/rotate`
- Bedrock keys: `POST /admin/access-keys/{id}/bedrock-key`

## Frontend overview
- Login: `/login`
- Users: `/users`, `/users/[id]`
- Usage dashboard: `/usage` (global view + per-user drilldown)

## Infra overview
CDK entry: `infra/app.py`. Stacks include VPC, Aurora Postgres Serverless v2,
ECS Fargate, ALB + ACM, Secrets Manager, KMS, CloudWatch.

## Tests
- `backend/tests/test_bedrock_converse.py` covers request/response conversion
  and event stream normalization.

## Known doc vs code gaps
- Admin auth in docs mentions bcrypt; code uses SHA-256 compare in
  `backend/src/api/admin_auth.py`.
- Cleanup jobs for rotated access keys are described but not implemented.
