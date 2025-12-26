# Project Structure

```
├── backend/                    # FastAPI backend service
│   ├── src/
│   │   ├── api/               # API route handlers
│   │   │   ├── admin_*.py     # Admin endpoints (auth, users, keys, usage)
│   │   │   ├── proxy_router.py # Main proxy endpoint
│   │   │   └── deps.py        # Dependency injection
│   │   ├── db/                # Database layer
│   │   │   ├── models.py      # SQLAlchemy ORM models
│   │   │   └── session.py     # Async session management
│   │   ├── domain/            # Domain logic
│   │   │   ├── entities.py    # Domain entities
│   │   │   ├── enums.py       # Enumerations
│   │   │   └── schemas.py     # Pydantic schemas
│   │   ├── proxy/             # Proxy logic
│   │   │   ├── bedrock_converse/  # Bedrock API adapter
│   │   │   ├── adapter_base.py    # Base adapter interface
│   │   │   ├── bedrock_adapter.py # Bedrock implementation
│   │   │   ├── plan_adapter.py    # Anthropic Plan adapter
│   │   │   ├── circuit_breaker.py # Failure handling
│   │   │   └── router.py          # Request routing logic
│   │   ├── repositories/      # Data access layer
│   │   ├── security/          # Encryption & key management
│   │   ├── config.py          # Settings (pydantic-settings)
│   │   ├── logging.py         # Structured logging setup
│   │   └── main.py            # FastAPI app entry point
│   ├── alembic/               # Database migrations
│   │   └── versions/          # Migration scripts
│   ├── tests/                 # pytest tests
│   └── pyproject.toml         # Python dependencies
│
├── frontend/                   # React admin dashboard
│   ├── src/
│   │   ├── pages/             # Page components
│   │   │   ├── LoginPage.tsx
│   │   │   ├── UsersPage.tsx
│   │   │   ├── UserDetailPage.tsx
│   │   │   └── UsagePage.tsx
│   │   ├── lib/               # Utilities
│   │   │   └── api.ts         # API client
│   │   ├── App.tsx            # Router setup
│   │   └── main.tsx           # Entry point
│   ├── scripts/               # Deployment scripts
│   └── package.json
│
├── infra/                      # AWS CDK infrastructure
│   ├── stacks/
│   │   ├── network_stack.py   # VPC, security groups
│   │   ├── database_stack.py  # RDS PostgreSQL
│   │   ├── compute_stack.py   # ECS Fargate service
│   │   ├── secrets_stack.py   # Secrets Manager, KMS
│   │   ├── monitoring_stack.py # CloudWatch alarms
│   │   └── amplify_stack.py   # Frontend hosting
│   └── app.py                 # CDK app entry point
│
└── docker-compose.yml          # Local development setup
```

## Architecture Patterns

- **Backend**: Layered architecture (API → Domain → Repository → DB)
- **Proxy**: Adapter pattern for multiple AI providers with circuit breaker
- **Frontend**: Page-based routing with centralized API client
- **Infra**: Multi-stack CDK with cross-stack references

## Key Files

- `backend/.env` - Backend environment variables
- `frontend/.env.local` - Frontend dev config
- `frontend/.env.production` - Frontend prod config
- `backend/alembic.ini` - Migration config

## Critical Code Locations

### Backend Entry Points
| File | Line Range | Purpose |
|------|-----------|---------|
| `backend/src/main.py` | Full file | FastAPI app initialization, CORS setup, router mounting |
| `backend/src/api/proxy_router.py` | 42-50 | Main proxy endpoint `/ak/{access_key}/v1/messages` |
| `backend/src/proxy/router.py` | 167-264 | Core routing logic: Plan → Bedrock fallback |

### Adapters (Provider Implementations)
| File | Key Responsibilities |
|------|---------------------|
| `backend/src/proxy/adapter_base.py` | Base interface for all adapters |
| `backend/src/proxy/plan_adapter.py` | Anthropic Plan API client (httpx-based) |
| `backend/src/proxy/bedrock_adapter.py` | Bedrock client (boto3-based, with KMS decryption) |
| `backend/src/proxy/bedrock_converse/` | Anthropic Messages ↔ Bedrock Converse translation |

### Database Layer
| File | Purpose |
|------|---------|
| `backend/src/db/models.py` | SQLAlchemy ORM models (5 tables) |
| `backend/src/db/session.py` | Async session factory |
| `backend/alembic/versions/001_initial_schema.py` | Initial DB schema migration |

### Security & Config
| File | Key Content |
|------|-------------|
| `backend/src/config.py` | Pydantic settings (all `PROXY_*` env vars) |
| `backend/src/security/encryption.py` | KMS envelope encryption for Bedrock credentials |
| `backend/src/security/keys.py` | Access key generation & HMAC hashing |
| `backend/src/proxy/auth.py` | Access key authentication middleware |

### Frontend Critical Files
| File | Purpose |
|------|---------|
| `frontend/src/lib/api.ts` | Type-safe API client, JWT token management |
| `frontend/src/App.tsx` | React Router setup, protected routes |
| `frontend/src/pages/UserDetailPage.tsx` | Most complex page: key management + Bedrock credential registration |

## Data Flow Diagrams

### Request Path (Successful Primary Route)
```
Client (Claude Code)
    ↓ POST /ak/{key}/v1/messages
proxy_router.py:42 (FastAPI endpoint)
    ↓ auth_service.authenticate_request()
auth.py:38 (validates access key)
    ↓ ProxyRouter.route()
router.py:167 (checks circuit breaker)
    ↓ PlanAdapter.forward()
plan_adapter.py:35 (httpx request)
    ↓ Anthropic Plan API
    ↓ 200 OK response
    ↓ usage_recorder.record()
usage.py:42 (save TokenUsageModel)
    ↓ return ProxyResponse
FastAPI streams response to client
```

### Fallback Path (Rate Limit → Bedrock)
```
... (same as above until Plan API) ...
    ↓ Anthropic Plan API
    ↓ 429 Rate Limit Error
router.py:210 (classifies error as retryable)
    ↓ circuit_breaker.should_fallback()
circuit_breaker.py:78 (checks state, records failure)
    ↓ BedrockAdapter.forward()
bedrock_adapter.py:68 (loads BedrockKey from cache/db)
    ↓ encryption.decrypt()
security/encryption.py:45 (KMS decrypt credentials)
    ↓ bedrock_converse/ (API translation)
    ↓ boto3.client('bedrock-runtime').converse()
    ↓ response translation
    ↓ usage_recorder.record(is_fallback=True)
    ↓ return ProxyResponse
```

## Important Patterns

### Repository Pattern
All DB access goes through repositories (`backend/src/repositories/`):
- `UserRepository` - CRUD for users
- `AccessKeyRepository` - Key management with caching
- `BedrockKeyRepository` - Encrypted credential storage
- `TokenUsageRepository` - Raw usage events
- `UsageAggregateRepository` - Pre-computed statistics

Benefits: Clean separation, easy to mock for tests, centralized caching

### Dependency Injection (FastAPI)
```python
# in proxy_router.py
async def proxy_messages(
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
):
    # session and auth_service auto-injected by FastAPI
```

All shared dependencies (DB session, config, services) use `Depends()` for testability.

### Async/Await Throughout
- All DB operations: `await session.execute(...)`
- All HTTP calls: `async with httpx.AsyncClient() as client`
- Streaming responses: `async for chunk in stream`

Performance benefit: Non-blocking I/O, high concurrency without threading

### Soft Delete Pattern
```python
# models.py
deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

# repositories use filters
.where(Model.deleted_at.is_(None))
```

### Environment Variable Naming
All backend config uses `PROXY_` prefix (defined in `config.py:45`):
```python
model_config = {"env_prefix": "PROXY_", "env_file": ".env"}
```

Example: `PROXY_DATABASE_URL`, `PROXY_JWT_SECRET`
