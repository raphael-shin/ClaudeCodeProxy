# Claude Code Proxy

Claude Code compatible proxy with automatic Bedrock fallback and a usage dashboard.

## Use the proxy (end users)
1) Ask your admin for an access key.
2) Point Claude Code at the proxy by setting `ANTHROPIC_BASE_URL`.
3) Keep your `ANTHROPIC_API_KEY` set to your Anthropic Plan key.

```bash
# Replace with your proxy host and access key
export ANTHROPIC_BASE_URL=https://proxy.example.com/ak/ak_your_access_key
export ANTHROPIC_API_KEY=your_anthropic_plan_key
```

Claude Code will send requests to the proxy automatically.

## What happens on each request
- The proxy forwards your request to Anthropic Plan using your `x-api-key`.
- If Plan is rate limited or fails, it can fall back to Amazon Bedrock Converse
  when a Bedrock key is registered for your access key.
- Usage is tracked for Bedrock responses and shown in the dashboard.

## Admin UI (operators)
- Create users and issue access keys.
- Register Bedrock keys for fallback.
- View usage by time range and timezone, with global totals and per-user drilldown.

## Operator runbook (quick)
1) Configure backend env vars in `backend/.env`:
   - Required: `PROXY_DATABASE_URL`, `PROXY_KEY_HASHER_SECRET`, `PROXY_JWT_SECRET`,
     `PROXY_ADMIN_USERNAME`, `PROXY_ADMIN_PASSWORD_HASH`
   - Optional: `PROXY_PLAN_API_KEY` (only if you want a default Plan key),
     `PROXY_BEDROCK_DEFAULT_MODEL`, `PROXY_PLAN_FORCE_RATE_LIMIT`
2) Run migrations:
   - `cd backend && alembic upgrade head`
3) Start services:
   - Backend: `uvicorn src.main:app --reload --port 8000`
   - Frontend: `cd ../frontend && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`
4) Verify health: `curl http://localhost:8000/health`
5) Admin workflow:
   - Login in `/login`, create users, issue access keys, register Bedrock keys.

## Running or extending the service
If you need local setup, deployment, or architecture details, see
`PROJECT_CONTEXT.md` and `aidlc-docs/`.
