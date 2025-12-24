# Tech Stack Decisions - ClaudeCodeProxy

## Backend

### Python + FastAPI

| Component | Version | Rationale |
|-----------|---------|-----------|
| Python | 3.11+ | Latest stable, async support |
| FastAPI | 0.100+ | High performance, async, OpenAPI |
| Uvicorn | 0.24+ | ASGI server |
| Pydantic | 2.0+ | Data validation |
| httpx | 0.25+ | Async HTTP client |

### Dependencies

```
# Core
fastapi>=0.100.0
uvicorn[standard]>=0.24.0
pydantic>=2.0.0
httpx>=0.25.0

# Database
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0
alembic>=1.12.0

# AWS
boto3>=1.34.0
aioboto3>=12.0.0

# Security
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4

# Utilities
python-dotenv>=1.0.0
structlog>=23.0.0
```

---

## Database

### Aurora PostgreSQL Serverless v2

| Setting | Value | Rationale |
|---------|-------|-----------|
| Engine | PostgreSQL 15 | Latest stable |
| Capacity | 0.5-4 ACU | Cost-effective scaling |
| Multi-AZ | Enabled | High availability |
| Encryption | Enabled | Security requirement |

### Connection Configuration

```python
DATABASE_CONFIG = {
    "pool_size": 5,
    "max_overflow": 5,
    "pool_timeout": 30,
    "pool_recycle": 1800,
    "echo": False
}
```

---

## Frontend

### Next.js

| Component | Version | Rationale |
|-----------|---------|-----------|
| Next.js | 14+ | App Router, RSC |
| React | 18+ | Latest stable |
| TypeScript | 5+ | Type safety |
| Tailwind CSS | 3+ | Utility-first styling |

### Dependencies

```json
{
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "recharts": "^2.10.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "tailwindcss": "^3.4.0",
    "@types/react": "^18.2.0"
  }
}
```

---

## Infrastructure

### AWS CDK (Python)

| Component | Version | Rationale |
|-----------|---------|-----------|
| AWS CDK | 2.100+ | Latest stable |
| Python | 3.11+ | Match backend |
| constructs | 10+ | CDK constructs |

### CDK Dependencies

```
aws-cdk-lib>=2.100.0
constructs>=10.0.0
```

### AWS Services

| Service | Purpose | Configuration |
|---------|---------|---------------|
| ECS Fargate | Compute | 0.5 vCPU, 1GB RAM |
| Aurora Serverless v2 | Database | 0.5-4 ACU |
| ALB | Load balancer | Multi-AZ |
| Secrets Manager | Secrets | Auto-rotation disabled |
| KMS | Encryption | Customer managed key |
| CloudWatch | Observability | Logs + Metrics |
| ACM | TLS certificates | Auto-renewal |
| VPC | Networking | 2 AZs, private subnets |

---

## Container

### Docker

| Setting | Value |
|---------|-------|
| Base image | python:3.11-slim |
| Multi-stage | Yes (build + runtime) |
| Non-root user | Yes |
| Health check | /health endpoint |

### Dockerfile Structure

```dockerfile
# Build stage
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY src/ ./src/
USER nobody
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Development Tools

| Tool | Purpose |
|------|---------|
| pytest | Testing |
| pytest-asyncio | Async test support |
| ruff | Linting + formatting |
| mypy | Type checking |
| pre-commit | Git hooks |

---

## Version Summary

| Component | Version |
|-----------|---------|
| Python | 3.11+ |
| FastAPI | 0.100+ |
| PostgreSQL | 15 |
| Next.js | 14+ |
| React | 18+ |
| AWS CDK | 2.100+ |
| Docker | 24+ |
