# Requirements Analysis - ClaudeCodeProxy

## Intent Analysis Summary

### User Request
Develop a ClaudeCodeProxy application - a proxy service that sits between Claude Code and Amazon Bedrock, providing automatic fallback from Anthropic Plan upstream to Bedrock when rate limits are hit.

### Request Type
**New Project** - Complete greenfield application development

### Scope Estimate
**System-wide** - Full-stack application including:
- Proxy API service
- Admin web interface
- Database layer
- AWS infrastructure deployment

### Complexity Estimate
**Complex** - Multi-component system with:
- API gateway/proxy functionality
- Authentication and authorization
- Key management and encryption
- Usage tracking and analytics
- Circuit breaker patterns
- Multi-provider integration (Anthropic + Bedrock)

---

## Technology Stack Decisions (Finalized)

| Component | Decision |
|-----------|----------|
| Backend | Python with FastAPI |
| Database | Amazon Aurora PostgreSQL Serverless v2 |
| Infrastructure as Code | AWS CDK (Python) |
| Admin UI | Next.js |
| Deployment | AWS ECS Express Mode |
| Secrets | AWS Secrets Manager |

---

## Functional Requirements

### FR-1: Claude Code Compatible Proxy
- **FR-1.1**: Accept Anthropic-style API requests at `POST /ak/{access_key}/v1/messages`
- **FR-1.2**: Support Anthropic `/v1/messages` request body format
- **FR-1.3**: Return Anthropic-compatible response format
- **FR-1.4**: Allow Claude Code to use proxy by changing only Base URL configuration

### FR-2: Automatic Provider Failover
- **FR-2.1**: Attempt Plan upstream call first for all requests
- **FR-2.2**: Detect failover conditions:
  - HTTP 429 status code
  - Rate limit error messages
  - Usage limit error messages
- **FR-2.3**: Automatically retry failed request to Bedrock **only if Bedrock API Key is configured**
- **FR-2.4**: If Bedrock API Key is NOT configured and Plan fails, return HTTP 503 with clear error message
- **FR-2.5**: Maintain Anthropic-compatible response schema during failover
- **FR-2.6**: Return Anthropic-compatible error response with internal request_id on complete failure
- **FR-2.7**: Classify Bedrock failures internally:
  - `bedrock_auth_error` - Authentication/authorization failures
  - `bedrock_quota_exceeded` - Quota/limit exceeded
  - `bedrock_unavailable` - Service unavailable or timeout

### FR-3: URL-Based User Identification
- **FR-3.1**: Extract Access Key from URL path parameter `{access_key}`
- **FR-3.2**: Validate Access Key exists and is active
- **FR-3.3**: Return 404 for invalid/revoked Access Keys
- **FR-3.4**: Do not use Authorization header for user identification

### FR-4: Circuit Breaker
- **FR-4.1**: Track Plan upstream failure rate per Access Key
- **FR-4.2**: Trigger circuit breaker after 3 consecutive Plan failures within 1 minute
- **FR-4.3**: Circuit breaker triggers on Plan failures only:
  - HTTP 429
  - HTTP 5xx errors
- **FR-4.4**: Bedrock failures do NOT contribute to circuit breaker state
- **FR-4.5**: Skip Plan upstream and route directly to Bedrock when circuit is open (if Bedrock API Key configured)
- **FR-4.6**: Reset circuit breaker after 30 minutes
- **FR-4.7**: Circuit breaker state must be observable via CloudWatch metrics

### FR-5: Bedrock Integration
- **FR-5.1**: Support user-configurable Bedrock region per Access Key (default: ap-northeast-2)
- **FR-5.2**: Support user-configurable Bedrock model per Access Key (default: global.anthropic.claude-sonnet-4-5-20250929-v1:0)
- **FR-5.3**: Transform Anthropic message format to Bedrock Converse API format
- **FR-5.4**: Transform Bedrock response to Anthropic-compatible format
- **FR-5.5**: Use user-specific Bedrock API Key (Bearer token) for authentication
- **FR-5.6**: Collect token usage metrics (input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens)

### FR-6: Admin - User Management
- **FR-6.1**: Create new users with name, description, status
- **FR-6.2**: View user list and details
- **FR-6.3**: Deactivate users
- **FR-6.4**: Store user metadata (name, description, status)

### FR-7: Admin - Access Key Management
- **FR-7.1**: Issue new Access Keys for users (1:N relationship)
- **FR-7.2**: Revoke Access Keys
- **FR-7.3**: Rotate Access Keys
- **FR-7.4**: Display Access Key prefix + masking (never full key after issuance)
- **FR-7.5**: Show full Access Key only once at creation time

### FR-8: Admin - Bedrock API Key Management
- **FR-8.1**: Register Bedrock API Key (Bearer token) per Access Key (1:1 relationship)
- **FR-8.2**: Rotate Bedrock API Keys
- **FR-8.3**: Display Bedrock API Key prefix + masking only
- **FR-8.4**: Never display full Bedrock API Key after registration

### FR-9: Admin - Usage Dashboard
- **FR-9.1**: Query Bedrock usage by user (Plan usage excluded - tracked by Claude Code plans)
- **FR-9.2**: Query Bedrock usage by Access Key (optional)
- **FR-9.3**: Support time bucket aggregations: minute, hour, day, week, month
- **FR-9.4**: Support custom date range selection
- **FR-9.5**: Display metrics: input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens, total_tokens
- **FR-9.6**: Dashboard tracks Bedrock provider usage only

### FR-10: Admin Authentication
- **FR-10.1**: Development: admin/admin credentials (dev environment only)
- **FR-10.2**: Production: Credentials stored in AWS Secrets Manager or OIDC integration
- **FR-10.3**: Password-based login
- **FR-10.4**: (OIDC/Cognito integration for production - phase 2)

---

## Non-Functional Requirements

### NFR-1: Performance
- **NFR-1.1**: Plan-only path latency: p95 < 100ms overhead
- **NFR-1.2**: Bedrock fallback path latency: p95 < 300-500ms overhead (including transformation)
- **NFR-1.3**: Support concurrent requests (no special handling - process all concurrently)
- **NFR-1.4**: Database query performance optimized with proper indexing

### NFR-2: Security
- **NFR-2.1**: Never expose Bedrock API Keys in URLs or logs
- **NFR-2.2**: Store Bedrock API Keys using KMS Envelope encryption
- **NFR-2.3**: Store Access Key hashes (not plaintext) in database
- **NFR-2.4**: Store Access Key prefix for UI display purposes
- **NFR-2.5**: Expose full Access Key only once at creation time
- **NFR-2.6**: Secure Plan upstream API key in AWS Secrets Manager
- **NFR-2.7**: Secure database credentials in AWS Secrets Manager
- **NFR-2.8**: Use HTTPS/TLS for all external communications
- **NFR-2.9**: CORS enabled - allow all origins

### NFR-3: Reliability
- **NFR-3.1**: Implement circuit breaker (3 failures/1 min trigger, 30 min reset)
- **NFR-3.2**: Graceful degradation when Plan upstream unavailable
- **NFR-3.3**: Automatic failover to Bedrock on Plan failures
- **NFR-3.4**: Simple /health endpoint (200 OK if service running)

### NFR-4: Scalability
- **NFR-4.1**: Horizontal scaling capability via ECS
- **NFR-4.2**: Database connection pooling
- **NFR-4.3**: Aurora Serverless v2 auto-scaling

### NFR-5: Maintainability
- **NFR-5.1**: Clear separation between Proxy and Admin functionality
- **NFR-5.2**: Modular architecture for provider integrations
- **NFR-5.3**: Configuration externalized (environment variables, Secrets Manager)

### NFR-6: Observability
- **NFR-6.1**: CloudWatch metrics (latency, error rate, request count)
- **NFR-6.2**: Track provider usage (plan vs bedrock)
- **NFR-6.3**: Monitor circuit breaker state
- **NFR-6.4**: Request tracing with unique request_id

---

## Data Requirements

### DR-1: Usage Metrics (Bedrock Only - No Raw Logs)
Store per-request Bedrock usage data only (Plan usage excluded):
- timestamp
- user_id
- access_key_id
- model
- input_tokens
- output_tokens
- cache_read_input_tokens
- cache_creation_input_tokens
- total_tokens

**Note**: No raw request/response bodies stored. Plan usage tracked by Claude Code plans. Detailed logs available via Bedrock Invocation Log.

### DR-2: Usage Aggregations
- Rollup tables for: minute, hour, day, month
- Minute rollups: retain 14 days
- Hour/day/month rollups: retain indefinitely
- Aggregated by: user_id, access_key_id, provider_used

### DR-3: User Data
- user_id (primary key)
- name
- description
- status (active/inactive)
- created_at
- updated_at

### DR-4: Access Key Data
- access_key_id (primary key)
- user_id (foreign key)
- key_hash (SHA-256)
- key_prefix (for UI display)
- status (active/revoked)
- bedrock_region (default: ap-northeast-2)
- bedrock_model (default: global.anthropic.claude-sonnet-4-5-20250929-v1:0)
- created_at
- revoked_at

### DR-5: Bedrock API Key Data
- access_key_id (foreign key, 1:1)
- encrypted_key (KMS envelope encrypted)
- key_hash (for validation)
- key_prefix (for UI display)
- created_at
- rotated_at

---

## Technical Specifications

### TS-1: Access Key Format
- **Prefix**: `ak_` (fixed)
- **Length**: 43-64 characters (32+ bytes)
- **Generation**: URL-safe UUID v4 with cryptographic randomness
- **Character Set**: URL-safe Base64 (A-Z, a-z, 0-9, -, _)
- **Example**: `ak_6D3h3X5R0pN1kQ9eU8mK7A2FZcLwYJtBvS-`

### TS-2: Bedrock API Key Format
- **Type**: Bedrock-scoped Bearer Token
- **Source**: Generated in Amazon Bedrock console or via Bedrock API
- **Usage**: `Authorization: Bearer <bedrock-api-key>`
- **Scope**: Limited to Bedrock and Bedrock Runtime operations
- **Note**: Not AWS IAM credentials - managed separately

### TS-3: API Endpoint
- **Proxy Endpoint**: `POST /ak/{access_key}/v1/messages`
- **Claude Code Configuration**: `ANTHROPIC_BASE_URL = https://proxy.example.com/ak/{access_key}`

### TS-4: Deployment Architecture
- **Platform**: AWS ECS Express Mode
- **Service Structure**: Single service containing Proxy + Admin
- **Load Balancer**: ALB for both Proxy and Admin endpoints
- **Database**: Amazon Aurora PostgreSQL Serverless v2
- **Secrets**: AWS Secrets Manager + KMS
- **Networking**: VPC with public ALB, private ECS tasks
- **Environment**: Single AWS account for all environments

### TS-5: Circuit Breaker Configuration
- **Trigger**: 3 consecutive Plan failures (429 or 5xx) within 1 minute
- **Reset Time**: 30 minutes
- **Scope**: Per Access Key
- **Trigger Source**: Plan upstream failures only (Bedrock failures excluded)
- **Observability**: Circuit breaker state exposed via CloudWatch metrics

---

## Constraints

### C-1: Authorization Header
- Authorization header is used by Claude Code for Plan upstream authentication
- Proxy cannot use Authorization header for user identification
- Must use URL-based Access Key for routing
- Proxy forwards Authorization or x-api-key upstream as-is (no conversion)

### C-2: Response Compatibility
- All responses must maintain Anthropic API compatibility
- Error responses must be Anthropic-compatible format
- Claude Code should experience minimal disruption during failover

### C-3: Security
- No API keys (Access Key or Bedrock API Key) in URLs except Access Key in path
- Bedrock API Keys never exposed in any external interface
- KMS encryption required for sensitive data at rest

### C-4: Deployment
- Single ECS service deployment (not microservices)
- Admin interface publicly accessible via ALB
- Must support horizontal scaling

### C-5: Rate Limiting
- No rate limiting implemented in Phase 1
- Budget-based limit policy may be added in future

---

## Success Criteria

### SC-1: Functional Success
- Claude Code can successfully use proxy with only Base URL change
- Automatic failover from Plan to Bedrock works seamlessly
- Admin can manage users, keys, and view usage data

### SC-2: Performance Success
- Proxy adds < 100ms latency for Plan calls
- Proxy adds < 200ms latency for Bedrock calls
- System handles concurrent users without special queuing

### SC-3: Security Success
- No API keys exposed in logs or URLs (except Access Key in path)
- All sensitive data encrypted at rest
- Access control properly enforced

### SC-4: Operational Success
- System deployed successfully to AWS ECS
- CloudWatch monitoring operational
- Usage data accurately tracked and aggregated

---

## Out of Scope (Phase 2)

- OIDC/Cognito authentication integration
- Multi-region deployment
- Advanced analytics and reporting
- User self-service portal
- Billing/cost allocation features
- Advanced circuit breaker strategies (per-model, per-region)
- Rate limiting / budget-based limits
