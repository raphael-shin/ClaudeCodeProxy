# Tech Stack

## Backend (Python)
- **Framework**: FastAPI 0.109+
- **Runtime**: Python 3.11+
- **Database**: PostgreSQL 15 with asyncpg driver
- **ORM**: SQLAlchemy 2.0+ (async mode)
- **Migrations**: Alembic
- **HTTP Client**: httpx (async)
- **AWS SDK**: boto3 (for Bedrock integration)
- **Auth**: python-jose (JWT), cryptography
- **Logging**: structlog
- **Config**: pydantic-settings (env prefix: `PROXY_`)

## Frontend (TypeScript)
- **Framework**: React 18
- **Build Tool**: Vite 5
- **Routing**: react-router-dom v6
- **Styling**: Tailwind CSS 3
- **Charts**: Recharts
- **Path Alias**: `@/` maps to `src/`

## Infrastructure
- **IaC**: AWS CDK (Python)
- **Compute**: ECS Fargate
- **Database**: RDS PostgreSQL
- **Frontend Hosting**: AWS Amplify
- **Secrets**: AWS Secrets Manager + KMS

## Common Commands

### Backend
```bash
cd backend

# Install dependencies
pip install -e ".[dev]"

# Run dev server
uvicorn src.main:app --reload --port 8000

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Run tests
pytest

# Linting
ruff check .
ruff format .

# Type checking
mypy src
```

### Frontend
```bash
cd frontend

# Install dependencies
npm ci

# Dev server (port 5173)
npm run dev

# Production build
npm run build

# Build zip for Amplify
npm run build:zip
```

### Infrastructure
```bash
cd infra

# Install dependencies
pip install -r requirements.txt

# Synthesize CloudFormation
cdk synth

# Deploy all stacks
cdk deploy --all
```

### Docker (Local Development)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend
```

## Development Environment Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or use Docker)
- AWS CLI (for Bedrock testing, optional)

### First-Time Backend Setup
```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Create .env file
cat > .env <<EOF
PROXY_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/proxy
PROXY_KEY_HASHER_SECRET=dev-secret-key-for-local-development
PROXY_JWT_SECRET=dev-jwt-secret-for-local-development
PROXY_ADMIN_USERNAME=admin
PROXY_ADMIN_PASSWORD_HASH=8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918
# ^ SHA256 hash of "admin" - change this!
PROXY_PLAN_API_KEY=sk-ant-api03-...  # Your Anthropic API key (optional)
PROXY_LOCAL_ENCRYPTION_KEY=dev-local-encryption-key-must-be-32-bytes-long!
EOF

# Start PostgreSQL (if using Docker)
docker run -d \
  --name proxy-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=proxy \
  -p 5432:5432 \
  postgres:15

# Run migrations
alembic upgrade head

# Start dev server
uvicorn src.main:app --reload --port 8000
```

### First-Time Frontend Setup
```bash
cd frontend

# Install dependencies
npm ci

# Create .env.local
echo "VITE_BACKEND_API_URL=http://localhost:8000" > .env.local

# Start dev server
npm run dev
# Opens at http://localhost:5173
```

### Generate Admin Password Hash
```bash
echo -n "your_password" | shasum -a 256
# Copy the hash to PROXY_ADMIN_PASSWORD_HASH
```

## Key Configuration Variables

### Backend Environment Variables (Prefix: `PROXY_`)

#### Required for Local Dev
| Variable | Example | Description |
|----------|---------|-------------|
| `PROXY_DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection string |
| `PROXY_KEY_HASHER_SECRET` | Random string | Salt for hashing access keys (HMAC) |
| `PROXY_JWT_SECRET` | Random string | Secret for signing admin JWT tokens |
| `PROXY_ADMIN_USERNAME` | `admin` | Admin login username |
| `PROXY_ADMIN_PASSWORD_HASH` | SHA256 hash | Hashed admin password |
| `PROXY_LOCAL_ENCRYPTION_KEY` | 32-byte string | Local fallback for KMS (dev only) |

#### Optional
| Variable | Default | Description |
|----------|---------|-------------|
| `PROXY_PLAN_API_KEY` | Empty | Default Anthropic API key (can be overridden per-user) |
| `PROXY_PLAN_API_URL` | `https://api.anthropic.com` | Anthropic API base URL |
| `PROXY_BEDROCK_REGION` | `ap-northeast-2` | AWS region for Bedrock |
| `PROXY_BEDROCK_DEFAULT_MODEL` | `global.anthropic.claude-sonnet-4-5...` | Bedrock model ID |
| `PROXY_KMS_KEY_ID` | Empty | AWS KMS key ID for prod encryption |
| `PROXY_CIRCUIT_FAILURE_THRESHOLD` | `3` | Failures before circuit opens |
| `PROXY_CIRCUIT_FAILURE_WINDOW` | `60` | Time window (seconds) for counting failures |
| `PROXY_CIRCUIT_RESET_TIMEOUT` | `1800` | Circuit breaker reset timeout (seconds) |
| `PROXY_ACCESS_KEY_CACHE_TTL` | `60` | Cache TTL for access key lookups (seconds) |
| `PROXY_BEDROCK_KEY_CACHE_TTL` | `300` | Cache TTL for Bedrock credentials (seconds) |

### Frontend Environment Variables (Prefix: `VITE_`)
| Variable | Example | Description |
|----------|---------|-------------|
| `VITE_BACKEND_API_URL` | `http://localhost:8000` | Backend API base URL |

## Database Schema Overview

### Tables (5 Total)
```sql
-- Core entities
users (id, email, hashed_password, created_at, updated_at, deleted_at)
access_keys (id, user_id, key_hash, is_active, created_at, deleted_at)
bedrock_keys (id, access_key_id, encrypted_access_key, encrypted_secret_key, region)

-- Usage tracking
token_usages (id, access_key_id, request_id, input_tokens, output_tokens,
              provider, is_fallback, latency_ms, created_at)
usage_aggregates (id, access_key_id, time_bucket, request_count,
                  total_input_tokens, total_output_tokens)
```

### Indexes
- `access_keys.key_hash` - Fast auth lookups
- `token_usages.access_key_id` - Fast usage queries per user
- `token_usages.created_at` - Time-range queries
- `usage_aggregates(access_key_id, time_bucket)` - Unique constraint for aggregation

### Foreign Keys
- `access_keys.user_id` → `users.id` (ON DELETE CASCADE)
- `bedrock_keys.access_key_id` → `access_keys.id` (ON DELETE CASCADE)
- `token_usages.access_key_id` → `access_keys.id` (ON DELETE SET NULL)

## Testing

### Backend Tests
```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_proxy_router.py -v

# Run with logs
pytest -s
```

### Frontend Tests
```bash
cd frontend

# Type check
npx tsc --noEmit

# Lint
npm run lint
```

## Common Debugging Scenarios

### "Access key not found" Error
1. Check `access_keys.key_hash` in DB matches HMAC hash of provided key
2. Verify `PROXY_KEY_HASHER_SECRET` matches between key creation and validation
3. Check key is not deleted (`deleted_at IS NULL`)

### Circuit Breaker Stuck Open
- Check `circuit_breaker_states` in-memory dict (not persisted to DB)
- Restart backend to reset all circuit breakers
- Or wait for `PROXY_CIRCUIT_RESET_TIMEOUT` (default 30 minutes)

### Bedrock Fallback Not Working
1. Verify `bedrock_keys` table has entry for the access key
2. Check KMS permissions if using AWS KMS
3. For local dev, ensure `PROXY_LOCAL_ENCRYPTION_KEY` is set
4. Check boto3 AWS credentials are valid (`aws sts get-caller-identity`)

### Migration Conflicts
```bash
# Downgrade to previous version
alembic downgrade -1

# Regenerate migration
alembic revision --autogenerate -m "description"

# Review the generated migration file before applying!
alembic upgrade head
```

## Useful SQL Queries

### View Recent Usage
```sql
SELECT
    ak.id as access_key_id,
    u.email,
    tu.provider,
    tu.is_fallback,
    tu.input_tokens,
    tu.output_tokens,
    tu.latency_ms,
    tu.created_at
FROM token_usages tu
JOIN access_keys ak ON tu.access_key_id = ak.id
JOIN users u ON ak.user_id = u.id
WHERE tu.created_at > NOW() - INTERVAL '1 hour'
ORDER BY tu.created_at DESC;
```

### Find High-Usage Users
```sql
SELECT
    u.email,
    COUNT(*) as request_count,
    SUM(tu.input_tokens + tu.output_tokens) as total_tokens
FROM token_usages tu
JOIN access_keys ak ON tu.access_key_id = ak.id
JOIN users u ON ak.user_id = u.id
WHERE tu.created_at > NOW() - INTERVAL '1 day'
GROUP BY u.email
ORDER BY total_tokens DESC
LIMIT 10;
```

### Check Fallback Rate
```sql
SELECT
    provider,
    is_fallback,
    COUNT(*) as request_count
FROM token_usages
WHERE created_at > NOW() - INTERVAL '1 day'
GROUP BY provider, is_fallback;
```
