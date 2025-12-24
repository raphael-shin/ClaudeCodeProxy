# Build Instructions

## Prerequisites

- **Python**: 3.11+
- **Node.js**: 18+
- **Docker & Docker Compose**: For local development
- **AWS CDK**: 2.x (for infrastructure deployment)
- **PostgreSQL**: 15+ (via Docker or local)

## Environment Variables

Create `.env` file in `backend/` directory:

```bash
PROXY_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/proxy
PROXY_KEY_HASHER_SECRET=your-secret-key-64-chars
PROXY_JWT_SECRET=your-jwt-secret-64-chars
PROXY_ADMIN_USERNAME=admin
PROXY_ADMIN_PASSWORD_HASH=sha256-hash-of-password
PROXY_KMS_KEY_ID=  # Optional for local dev (AWS KMS)
PROXY_LOCAL_ENCRYPTION_KEY=  # Optional for local dev (fallback when KMS not used)
PROXY_BEDROCK_DEFAULT_MODEL=global.anthropic.claude-sonnet-4-5-20250929-v1:0
PROXY_PLAN_VERIFY_SSL=true  # Optional: set false to bypass TLS verify in local debug
PROXY_PLAN_CA_BUNDLE=  # Optional: custom CA bundle path for Plan TLS
PROXY_PLAN_FORCE_RATE_LIMIT=false  # Optional: simulate Plan 429 for fallback testing

# PROXY_PLAN_API_KEY is NOT required
# Client's Authorization or x-api-key header is forwarded to Anthropic Plan API
```

---

## Build Steps

### 1. Start Local Services (Database)

```bash
cd /Users/jungseob/workspace/ClaudeCodeProxy
docker-compose up -d postgres
```

### 2. Install Backend Dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 3. Run Database Migrations

```bash
cd backend
alembic upgrade head
```

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 5. Build Frontend

```bash
cd frontend
npm run build
```

---

## Verify Build Success

### Backend
```bash
cd backend
python -c "from src.main import app; print('Backend OK')"
```

### Frontend
```bash
cd frontend
ls -la .next/  # Should contain build output
```

---

## Run Services Locally

### Start Backend
```bash
cd backend
uvicorn src.main:app --reload --port 8000
```

### Start Frontend (Development)
```bash
cd frontend
npm run dev
```

---

## Troubleshooting

### Database Connection Error
- Ensure PostgreSQL is running: `docker-compose ps`
- Check connection string in `.env`
- Verify database exists: `docker-compose exec postgres psql -U postgres -c '\l'`

### Migration Errors
- Check alembic version: `alembic current`
- Reset if needed: `alembic downgrade base && alembic upgrade head`

### Frontend Build Errors
- Clear cache: `rm -rf .next node_modules && npm install`
- Check Node version: `node --version` (should be 18+)
