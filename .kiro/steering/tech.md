---
inclusion: always
---

# Tech Stack & Development Guide

## Stack Overview

| Layer | Technologies |
|-------|-------------|
| Backend | FastAPI 0.109+, Python 3.11+, SQLAlchemy 2.0 (async), PostgreSQL 15, asyncpg |
| Frontend | React 18, Vite 5, TypeScript, Tailwind CSS 3, react-router-dom v6 |
| Infrastructure | AWS CDK (Python), ECS Fargate, RDS PostgreSQL, Amplify, KMS |

## Code Conventions

### Python (Backend)
- ALL database and HTTP operations MUST use `async/await`
- Type hints REQUIRED on all function signatures
- Environment variables MUST use `PROXY_` prefix
- Use `httpx` for async HTTP, `boto3` for AWS SDK
- Logging via `structlog` (structured JSON)
- Config via `pydantic-settings` with validation

### TypeScript (Frontend)
- Import paths: use `@/` alias (maps to `src/`)
- API calls: centralize in `lib/api.ts`
- Styling: Tailwind utility classes only

### Database Patterns
- Soft delete: set `deleted_at` timestamp, filter with `.where(Model.deleted_at.is_(None))`
- Access keys: stored as HMAC-SHA256 hash (never plaintext)
- Bedrock credentials: KMS envelope encryption required
- All queries MUST be async (`await session.execute(...)`)

## Essential Commands

```bash
# Backend (from backend/)
pip install -e ".[dev]"           # Install deps
uvicorn src.main:app --reload     # Dev server :8000
alembic upgrade head              # Run migrations
alembic revision --autogenerate -m "desc"  # New migration
pytest                            # Tests
ruff check . && ruff format .     # Lint/format
mypy src                          # Type check

# Frontend (from frontend/)
npm ci                            # Install deps
npm run dev                       # Dev server :5173
npm run build                     # Production build

# Docker
docker-compose up -d              # Full stack
docker-compose up db              # DB only
```

## Environment Variables

### Backend (Required)
| Variable | Purpose |
|----------|---------|
| `PROXY_DATABASE_URL` | PostgreSQL async connection string |
| `PROXY_KEY_HASHER_SECRET` | HMAC salt for access key hashing |
| `PROXY_JWT_SECRET` | Admin JWT signing secret |
| `PROXY_ADMIN_USERNAME` | Admin login username |
| `PROXY_ADMIN_PASSWORD_HASH` | SHA256 hash of admin password |
| `PROXY_LOCAL_ENCRYPTION_KEY` | 32-byte key for local dev (KMS fallback) |

### Backend (Optional)
| Variable | Default | Purpose |
|----------|---------|---------|
| `PROXY_PLAN_API_KEY` | - | Anthropic API key |
| `PROXY_BEDROCK_REGION` | `ap-northeast-2` | AWS Bedrock region |
| `PROXY_CIRCUIT_FAILURE_THRESHOLD` | `3` | Failures before circuit opens |
| `PROXY_CIRCUIT_RESET_TIMEOUT` | `1800` | Circuit reset (seconds) |

### Frontend
| Variable | Purpose |
|----------|---------|
| `VITE_BACKEND_API_URL` | Backend API base URL |

## Database Schema

5 tables: `users`, `access_keys`, `bedrock_keys`, `token_usages`, `usage_aggregates`

Key relationships:
- `access_keys.user_id` → `users.id` (CASCADE)
- `bedrock_keys.access_key_id` → `access_keys.id` (CASCADE)
- `token_usages.access_key_id` → `access_keys.id` (SET NULL)

## Debugging Quick Reference

| Issue | Check |
|-------|-------|
| "Access key not found" | Verify `key_hash` matches HMAC of key, check `deleted_at IS NULL` |
| Circuit breaker stuck | In-memory state; restart backend or wait for timeout |
| Bedrock fallback fails | Check `bedrock_keys` entry exists, verify AWS creds, check KMS perms |
| Migration conflict | `alembic downgrade -1`, regenerate, review diff, `alembic upgrade head` |

## Testing

```bash
# Backend
pytest                           # All tests
pytest --cov=src                 # With coverage
pytest tests/test_file.py -v     # Specific file

# Frontend
npx tsc --noEmit                 # Type check
npm run lint                     # ESLint
```
