# Unit of Work Definitions - ClaudeCodeProxy

## Overview

ClaudeCodeProxy is decomposed into 8 units of work plus a shared foundation module.

---

## Shared Foundation (Not a Unit - Foundation Layer)

### Purpose
Provides common types, utilities, and data access layer used by all units.

### Components
- **Core Types**: RequestContext, error enums, DTOs
- **Config**: Environment configuration, secrets loading
- **Logging**: Structured logging with masking
- **Database**: Session factory, connection pooling
- **Repositories**: Repository interfaces and implementations
- **Security**: KeyHasher (HMAC), KeyMasker, KeyGenerator

### Technology
- Python 3.11+
- SQLAlchemy 2.0 (async)
- Pydantic v2
- boto3 (AWS SDK)

### Schema Migrations
- Alembic migrations owned by shared module
- Applied during deployment (not CDK)

---

## Unit 1A: Request Ingress & Authentication

### Purpose
Handle incoming HTTP requests, validate Access Keys, create authenticated context.

### Responsibilities
- Extract `{access_key}` from URL path
- Hash key with HMAC and lookup in database
- Check cache before database query
- Validate key status (active/revoked)
- Generate unique `request_id`
- Create `RequestContext` with user/key metadata
- Return 404 for invalid keys

### Inputs
- HTTP Request: `POST /ak/{access_key}/v1/messages`
- Request body: Anthropic-compatible JSON

### Outputs
- `RequestContext` (success) or HTTP 404 (failure)

### Dependencies
- Shared: AccessKeyRepository, AccessKeyCache, KeyHasher
- Runtime: Database, Secrets Manager

### Technology
- FastAPI
- httpx (async HTTP)

### Test Strategy
- Unit tests: Mock repository and cache
- Contract tests: Validate RequestContext schema

---

## Unit 1B: Plan Upstream Adapter

### Purpose
Handle communication with Anthropic Plan upstream API.

### Responsibilities
- Transform internal request to Anthropic API format
- Invoke Plan upstream with client Authorization/x-api-key (default)
- Optionally inject a default Plan API key when configured
- Parse and normalize responses
- Classify errors (rate_limit, server_error, etc.)
- Detect failover signals (429, 5xx)

### Inputs
- `RequestContext`
- `AnthropicRequest`

### Outputs
- `AdapterResponse` (success) or `AdapterError` (failure)

### Dependencies
- Shared: Config (optional Plan API key)
- Runtime: Anthropic API

### Technology
- httpx (async HTTP client)
- Pydantic (request/response models)

### Test Strategy
- Unit tests: Mock HTTP responses
- Contract tests: Validate AdapterResponse/AdapterError schema

### Key Guarantee
- Does NOT know about Bedrock or fallback logic

---

## Unit 1C: Bedrock Adapter

### Purpose
Handle communication with Amazon Bedrock Converse API.

### Responsibilities
- Transform Anthropic request to Bedrock Converse format
- Retrieve decrypted Bedrock API Key (with cache)
- Invoke Bedrock Runtime Converse endpoint with Bearer token
- Transform Bedrock response to Anthropic format
- Extract token usage metrics
- Classify Bedrock errors

### Inputs
- `RequestContext`
- `AnthropicRequest`

### Outputs
- `AdapterResponse` (success) or `AdapterError` (failure)

### Dependencies
- Shared: BedrockKeyService, BedrockKeyCache
- Runtime: Bedrock Runtime API, KMS

### Technology
- httpx (async HTTP client)
- boto3 (KMS decrypt)

### Test Strategy
- Unit tests: Mock Bedrock responses and KMS
- Contract tests: Validate response transformation accuracy

### Key Guarantee
- Pure Bedrock concern only
- No routing or circuit logic

---

## Unit 1D: Routing & Circuit Breaker

### Purpose
Decide execution path and manage circuit breaker state.

### Responsibilities
- Determine execution path (Plan only, Plan→Bedrock, Bedrock direct)
- Maintain per-Access-Key circuit breaker state
- Track Plan failures (429, 5xx only)
- Apply failover policy
- Ignore Bedrock failures for circuit state

### Inputs
- `RequestContext`
- `AnthropicRequest`

### Outputs
- `ProxyResponse` (final response to client)

### Dependencies
- Unit 1B: PlanAdapter (via protocol)
- Unit 1C: BedrockAdapter (via protocol)
- Shared: CircuitBreaker state store

### Technology
- In-memory circuit state (per-process)
- Protocol-based adapter injection

### Test Strategy
- Unit tests: Mock adapters, test all routing paths
- Contract tests: Validate circuit breaker state transitions

### Configuration
- Trigger: 3 consecutive Plan failures (429/5xx) in 1 minute
- Reset: 30 minutes

---

## Unit 1E: Usage Metering & Observability

### Purpose
Record usage metrics and emit observability data.

### Responsibilities
- Always record request logs (Plan + Bedrock outcomes)
- Record token usage for Bedrock success only
- Measure latency per execution stage
- Emit CloudWatch metrics
- Log request outcomes for debugging

### Inputs
- `RequestContext`
- `ProxyResponse`
- Timing data

### Outputs
- None (side-effect only)

### Dependencies
- Shared: RequestLogRepository, TokenUsageRepository
- Runtime: CloudWatch

### Technology
- boto3 (CloudWatch)
- Async background tasks

### Test Strategy
- Unit tests: Mock repositories and CloudWatch
- Contract tests: Validate log/metric schemas

### Key Guarantee
- Side-effect only
- Does NOT influence routing decisions

---

## Unit 2: Admin Backend

### Purpose
Provide REST API for admin operations.

### Responsibilities
- User CRUD (create, read, deactivate)
- Access Key management (issue, revoke, rotate)
- Bedrock API Key management (register, rotate)
- Usage dashboard data queries
- Admin authentication

### Inputs
- HTTP REST requests

### Outputs
- JSON responses

### Dependencies
- Shared: All repositories, services
- Runtime: Database, Secrets Manager, KMS

### Technology
- FastAPI
- Pydantic
- python-jose (JWT sessions)

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | /admin/auth/login | Admin login |
| GET | /admin/users | List users |
| POST | /admin/users | Create user |
| GET | /admin/users/{id} | Get user |
| PATCH | /admin/users/{id} | Update user |
| POST | /admin/users/{id}/access-keys | Issue Access Key |
| DELETE | /admin/access-keys/{id} | Revoke Access Key |
| POST | /admin/access-keys/{id}/rotate | Rotate Access Key |
| POST | /admin/access-keys/{id}/bedrock-key | Register Bedrock Key |
| GET | /admin/usage | Query usage data |

### Test Strategy
- Unit tests: Mock services
- Contract tests: OpenAPI schema validation
- Integration tests: Full API flow with test DB

---

## Unit 3: Admin Frontend

### Purpose
Next.js web application for admin operations.

### Responsibilities
- Login page and session management
- User management UI
- Access Key management UI
- Bedrock API Key management UI
- Usage dashboard with charts

### Inputs
- User interactions

### Outputs
- Rendered UI

### Dependencies
- Unit 2: Admin Backend API (runtime)

### Technology
- Next.js 14+ (App Router)
- React 18
- TypeScript
- Tailwind CSS
- Chart.js or Recharts

### Pages
| Path | Description |
|------|-------------|
| /login | Admin authentication |
| /users | User list |
| /users/[id] | User detail with keys |
| /usage | Usage dashboard |

### Test Strategy
- Unit tests: Component tests with React Testing Library
- Contract tests: API response mocking
- E2E tests: Playwright (optional)

---

## Unit 4: Infrastructure

### Purpose
AWS CDK infrastructure as code.

### Sub-Units
- **Infra-A (Foundation)**: VPC, Aurora, KMS, Secrets, base ECS
- **Infra-B (Service Binding)**: ECS service wiring, ALB, autoscaling, alarms

### Responsibilities
- VPC and networking
- Aurora PostgreSQL Serverless v2
- ECS Fargate cluster and services
- Application Load Balancer
- AWS Secrets Manager
- KMS key for encryption
- CloudWatch log groups and dashboards

### Technology
- AWS CDK (Python)
- Docker (container images)

### Stacks
| Stack | Description | Phase |
|-------|-------------|-------|
| NetworkStack | VPC, subnets, security groups | Infra-A |
| DatabaseStack | Aurora Serverless v2 | Infra-A |
| SecretsStack | Secrets Manager, KMS | Infra-A |
| ComputeStack | ECS Fargate, ALB | Infra-B |
| MonitoringStack | CloudWatch dashboards, alarms | Infra-B |

### Test Strategy
- CDK synth validation
- cfn-lint for CloudFormation
- Integration tests with localstack (optional)

---

## Unit Summary

| Unit | Type | LOC Estimate | Complexity |
|------|------|--------------|------------|
| Shared | Foundation | 800-1000 | Medium |
| 1A | Module | 200-300 | Low |
| 1B | Module | 300-400 | Medium |
| 1C | Module | 400-500 | Medium |
| 1D | Module | 300-400 | Medium |
| 1E | Module | 200-300 | Low |
| 2 | Service | 600-800 | Medium |
| 3 | Service | 1000-1500 | Medium |
| 4 | CDK | 500-700 | Medium |
