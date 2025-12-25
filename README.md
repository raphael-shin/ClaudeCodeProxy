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

## Local frontend testing (Vite)
1) Create `frontend/.env.local`:
   - `VITE_BACKEND_API_URL=http://localhost:8000`
2) Install dependencies:
   - `cd frontend`
   - `npm ci`
3) Start dev server:
   - `npm run dev`
4) Open the app:
   - `http://localhost:5173`
5) If you change `.env.local`, restart the dev server to pick up new values.

## Frontend deployment (Amplify)

### Option A: CLI 스크립트 (권장)

하나의 스크립트로 첫 배포와 업데이트 배포를 자동 처리합니다.

Prerequisites:
- AWS CLI 설치 및 인증 설정 (`aws configure`)
- `frontend/.env.production`에 `VITE_BACKEND_API_URL` 설정

```bash
cd frontend
npm ci
npm run deploy:amplify:init
```

환경변수 옵션:
- `APP_NAME` - 앱 이름 (기본: `claude_code_proxy`)
- `BRANCH` - 브랜치명 (기본: `main`)
- `AWS_REGION` - 리전 (기본: `ap-northeast-2`)
- `SKIP_BUILD=1` - 빌드 스킵 (이미 dist.zip이 있을 때)

### Option B: Amplify Console 수동 업로드

1) `frontend/.env.production` 설정:
   ```
   VITE_BACKEND_API_URL=http://<ALB_DNS_NAME>
   ```
2) 빌드:
   ```bash
   cd frontend && npm ci && npm run build:zip
   ```
3) Amplify Console에서 `dist.zip` 업로드 (Manual deploy)
4) Rewrites and redirects 설정:
   - Source: `</^[^.]+$|\.(?!(js|css|ico|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot|json|map)$)([^.]+$)/>`
   - Target: `/index.html`
   - Type: `200 (Rewrite)`

### Option C: Git 연동

Amplify CLI로 GitHub 연동 후 자동 배포:
```bash
cd frontend
amplify init
amplify hosting add  # GitHub 선택
amplify publish
```

Amplify Console에서 환경변수 `VITE_BACKEND_API_URL` 설정 필요.

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
   - Frontend: `cd ../frontend && npm run dev` (use `frontend/.env.local` for `VITE_BACKEND_API_URL`)
4) Verify health: `curl http://localhost:8000/health`
5) Admin workflow:
   - Login in `/login`, create users, issue access keys, register Bedrock keys.

## Running or extending the service
If you need local setup, deployment, or architecture details, see
`PROJECT_CONTEXT.md` and `aidlc-docs/`.
