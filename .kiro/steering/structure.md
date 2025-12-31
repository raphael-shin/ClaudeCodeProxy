---
inclusion: always
---

# Project Structure & Architecture

## Directory Layout

```
backend/                        # FastAPI backend (Python 3.11+)
├── src/
│   ├── api/                   # Route handlers
│   │   ├── admin_*.py         # Admin endpoints
│   │   ├── proxy_router.py    # Main proxy endpoint
│   │   └── deps.py            # FastAPI dependencies
│   ├── db/                    # Database layer
│   │   ├── models.py          # SQLAlchemy ORM models
│   │   └── session.py         # Async session factory
│   ├── domain/                # Business logic
│   │   ├── entities.py        # Domain entities
│   │   ├── enums.py           # Enumerations
│   │   └── schemas.py         # Pydantic schemas
│   ├── proxy/                 # Proxy routing logic
│   │   ├── bedrock_converse/  # Bedrock API translation
│   │   ├── adapter_base.py    # Base adapter interface
│   │   ├── bedrock_adapter.py # Bedrock implementation
│   │   ├── plan_adapter.py    # Anthropic Plan adapter
│   │   ├── circuit_breaker.py # Failure handling
│   │   └── router.py          # Request routing
│   ├── repositories/          # Data access layer
│   ├── security/              # Encryption & keys
│   ├── config.py              # Settings (pydantic-settings)
│   └── main.py                # App entry point
├── alembic/versions/          # DB migrations
└── tests/                     # pytest tests

frontend/                       # React admin dashboard (TypeScript)
├── src/
│   ├── pages/                 # Page components
│   ├── lib/api.ts             # API client
│   ├── App.tsx                # Router setup
│   └── main.tsx               # Entry point
└── scripts/                   # Deployment scripts

infra/                          # AWS CDK (Python)
├── stacks/                    # CDK stack definitions
└── app.py                     # CDK entry point
```

## Architecture Patterns

### Layered Architecture (Backend)
```
API Layer → Domain Layer → Repository Layer → Database
```
- API handlers call domain services
- Domain contains business logic and Pydantic schemas
- Repositories handle all DB operations
- Never bypass layers (e.g., no direct DB access from API)

### Adapter Pattern (Proxy)
- `AdapterBase` defines interface for AI providers
- `PlanAdapter` implements Anthropic Plan API
- `BedrockAdapter` implements AWS Bedrock
- Add new providers by implementing `AdapterBase`

### Repository Pattern
All DB access through `backend/src/repositories/`:
- `UserRepository` - User CRUD
- `AccessKeyRepository` - Key management + caching
- `BedrockKeyRepository` - Encrypted credentials
- `TokenUsageRepository` - Usage events
- `UsageAggregateRepository` - Aggregated stats

## Code Conventions

### Backend (Python)
- Use `async/await` for all DB and HTTP operations
- Type hints required on all functions
- Environment variables use `PROXY_` prefix
- Soft delete: use `deleted_at` column, filter with `.where(Model.deleted_at.is_(None))`
- Dependencies via FastAPI `Depends()` for testability

### Frontend (TypeScript)
- Path alias: `@/` maps to `src/`
- Centralized API client in `lib/api.ts`
- Page-based routing with react-router-dom v6

### Database
- PostgreSQL 15 with asyncpg driver
- SQLAlchemy 2.0 async mode
- Alembic for migrations
- 5 tables: `users`, `access_keys`, `bedrock_keys`, `token_usages`, `usage_aggregates`

## Key Entry Points

| Task | File |
|------|------|
| Add API endpoint | `backend/src/api/` |
| Modify proxy logic | `backend/src/proxy/router.py` |
| Add DB model | `backend/src/db/models.py` |
| Add repository | `backend/src/repositories/` |
| Modify config | `backend/src/config.py` |
| Add frontend page | `frontend/src/pages/` |
| Add CDK stack | `infra/stacks/` |

## Request Flow

```
POST /ak/{access_key}/v1/messages
    → proxy_router.py (auth via access key)
    → router.py (circuit breaker check)
    → PlanAdapter (primary) or BedrockAdapter (fallback)
    → usage.py (record tokens)
    → stream response to client
```

## When Adding New Features

1. **New API endpoint**: Create handler in `api/`, add to router in `main.py`
2. **New DB table**: Add model in `db/models.py`, create Alembic migration
3. **New repository**: Implement in `repositories/`, inject via `Depends()`
4. **New AI provider**: Implement `AdapterBase` in `proxy/`
5. **New frontend page**: Add component in `pages/`, update `App.tsx` routes
