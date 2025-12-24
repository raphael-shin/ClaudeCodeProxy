# Components - ClaudeCodeProxy

## Project Structure

```
claude-code-proxy/
├── src/
│   ├── proxy/           # Unit 1A-1E: Proxy components
│   ├── admin/           # Unit 2: Admin Backend
│   └── shared/          # Shared models, repositories, utils
├── admin-ui/            # Unit 3: Next.js Admin Frontend
└── infra/               # Unit 4: AWS CDK Infrastructure
```

---

## Unit 1A: Request Ingress & Authentication

### Purpose
Handle incoming HTTP requests, extract and validate Access Keys, and create authenticated request context.

### Responsibilities
- Extract `{access_key}` from URL path `/ak/{access_key}/v1/messages`
- Validate Access Key existence and status (active/revoked)
- Look up associated user and Bedrock configuration
- Generate unique `request_id` for tracing
- Create `RequestContext` with authentication data
- Return 404 for invalid/revoked keys

### Interfaces
- **Input**: Raw HTTP Request
- **Output**: `RequestContext` (authenticated) or HTTP 404 error

### Key Classes
- `IngressHandler` - FastAPI route handler
- `AccessKeyValidator` - Key validation logic
- `RequestContext` - Authenticated context dataclass

---

## Unit 1B: Plan Upstream Adapter

### Purpose
Handle communication with Anthropic Plan upstream API.

### Responsibilities
- Transform internal request to Anthropic API format
- Invoke Plan upstream with client Authorization/x-api-key (default)
- Optionally inject a default Plan API key when configured
- Parse and normalize Plan responses
- Detect rate-limit signals (HTTP 429, usage limit errors)
- Return normalized response or error classification

### Interfaces
- **Input**: `RequestContext`, `AnthropicRequest`
- **Output**: `AdapterResponse` (success) or `AdapterError` (with classification)

### Key Classes
- `PlanAdapter` (implements `UpstreamAdapter` protocol)
- `AnthropicRequest` / `AnthropicResponse` DTOs
- `PlanError` - Error classification

### Key Guarantee
- Does NOT know about Bedrock or fallback logic

---

## Unit 1C: Bedrock Adapter

### Purpose
Handle communication with Amazon Bedrock Converse API.

### Responsibilities
- Transform internal request to Bedrock Converse format
- Retrieve and decrypt Bedrock API Key for Access Key
- Invoke Bedrock Runtime Converse endpoint with Bearer token
- Transform Bedrock response to Anthropic-compatible format
- Extract token usage (input, output, cache tokens)
- Classify Bedrock errors (auth, quota, unavailable)

### Interfaces
- **Input**: `RequestContext`, `AnthropicRequest`
- **Output**: `AdapterResponse` (success) or `AdapterError` (with classification)

### Key Classes
- `BedrockAdapter` (implements `UpstreamAdapter` protocol)
- `BedrockConverseRequest` / `BedrockConverseResponse` DTOs
- `BedrockError` - Error classification (auth_error, quota_exceeded, unavailable)

### Key Guarantee
- Pure Bedrock concern only
- No routing or circuit logic

---

## Unit 1D: Routing & Circuit Breaker

### Purpose
Decide execution path and manage circuit breaker state.

### Responsibilities
- Determine execution path:
  - Plan only (circuit closed, no BAK)
  - Plan → Bedrock fallback (circuit closed, has BAK)
  - Bedrock direct (circuit open, has BAK)
- Maintain per-Access-Key circuit breaker state
- Track Plan failures (429, 5xx) for circuit triggering
- Apply failover policy when Plan fails
- Ignore Bedrock failures for circuit state

### Interfaces
- **Input**: `RequestContext`, `AnthropicRequest`
- **Output**: `ProxyResponse` (final response to client)

### Key Classes
- `Router` - Orchestrates adapter calls
- `CircuitBreaker` - Per-key circuit state management
- `CircuitState` - Enum (CLOSED, OPEN, HALF_OPEN)

### Configuration
- Trigger: 3 consecutive Plan failures in 1 minute
- Reset: 30 minutes

---

## Unit 1E: Usage Metering & Observability

### Purpose
Record usage metrics and emit observability data.

### Responsibilities
- Measure latency per execution stage
- Record Bedrock token usage (input, output, cache tokens)
- Persist usage records to database
- Emit CloudWatch metrics (fallback rate, error rate, latency)
- Log request outcomes for debugging

### Interfaces
- **Input**: `RequestContext`, `AdapterResponse`, timing data
- **Output**: None (side-effect only)

### Key Classes
- `UsageRecorder` - Persist usage to database
- `MetricsEmitter` - CloudWatch metrics
- `UsageRecord` - Usage data model

### Key Guarantee
- Side-effect only
- Does NOT influence routing decisions

---

## Unit 2: Admin Backend

### Purpose
Provide REST API for admin operations (user, key, usage management).

### Responsibilities
- User CRUD operations (create, read, deactivate)
- Access Key management (issue, revoke, rotate)
- Bedrock API Key management (register, rotate)
- Usage dashboard data queries
- Admin authentication

### Interfaces
- **Input**: HTTP REST requests
- **Output**: JSON responses

### Key Classes
- `UserService` - User management logic
- `AccessKeyService` - Access Key operations
- `BedrockKeyService` - Bedrock API Key operations
- `UsageService` - Usage data queries
- `AuthService` - Admin authentication

### API Endpoints
- `POST /admin/users` - Create user
- `GET /admin/users` - List users
- `GET /admin/users/{id}` - Get user
- `PATCH /admin/users/{id}` - Update user
- `POST /admin/users/{id}/access-keys` - Issue Access Key
- `DELETE /admin/access-keys/{id}` - Revoke Access Key
- `POST /admin/access-keys/{id}/bedrock-key` - Register Bedrock Key
- `GET /admin/usage` - Query usage data

---

## Unit 3: Admin Frontend

### Purpose
Next.js web application for admin operations.

### Responsibilities
- Login page and session management
- User management UI (list, create, deactivate)
- Access Key management UI (issue, revoke, rotate)
- Bedrock API Key management UI (register, rotate)
- Usage dashboard with charts and filters

### Key Pages
- `/login` - Admin authentication
- `/users` - User list and management
- `/users/[id]` - User detail with keys
- `/usage` - Usage dashboard

### Technology
- Next.js 14+ with App Router
- React Server Components where applicable
- Client-side data fetching for interactive features

---

## Unit 4: Infrastructure

### Purpose
AWS CDK infrastructure as code.

### Responsibilities
- VPC and networking setup
- ECS Fargate service for Proxy + Admin
- Aurora PostgreSQL Serverless v2
- Application Load Balancer
- AWS Secrets Manager for credentials
- KMS key for Bedrock API Key encryption
- CloudWatch log groups and dashboards

### Key Stacks
- `NetworkStack` - VPC, subnets, security groups
- `DatabaseStack` - Aurora Serverless v2
- `SecretsStack` - Secrets Manager, KMS
- `ComputeStack` - ECS Fargate, ALB
- `MonitoringStack` - CloudWatch dashboards, alarms

### Technology
- AWS CDK (Python)
