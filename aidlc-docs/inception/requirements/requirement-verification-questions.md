# Requirements Verification Questions

Please answer the following questions to clarify and verify the requirements for ClaudeCodeProxy.

---

## Question 1: Backend Technology Stack
What backend language/framework should be used for the proxy service?

A) Node.js with Express/Fastify
B) Python with FastAPI/Flask
C) Go
D) Java with Spring Boot
E) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 2: Database Selection
Which database should be used for storing users, keys, and usage data?

A) PostgreSQL
B) MySQL
C) Amazon DynamoDB
D) Amazon Aurora (PostgreSQL-compatible Serverless v2)
E) Other (please describe after [Answer]: tag below)

[Answer]: D

---

## Question 3: Infrastructure as Code
What tool should be used for infrastructure provisioning?

A) AWS CDK (TypeScript)
B) AWS CDK (Python)
C) Terraform
D) AWS CloudFormation
E) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Question 4: Circuit Breaker Thresholds
What should trigger the circuit breaker to skip Plan upstream?

A) 3 consecutive 429 errors within 1 minute
B) 5 consecutive 429 errors within 5 minutes
C) 10 failures within 10 minutes (any Access Key)
D) 50% failure rate over 5 minutes (global)
E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 5: Circuit Breaker Reset Time
How long should the circuit breaker stay open before attempting Plan upstream again?

A) 1 minute
B) 5 minutes
C) 15 minutes
D) 30 minutes
E) Other (please describe after [Answer]: tag below)

[Answer]: D

---

## Question 6: Admin UI Framework
What should be used for the Admin web interface?

A) React
B) Vue.js
C) Server-side rendered (EJS/Pug templates)
D) Next.js
E) Other (please describe after [Answer]: tag below)

[Answer]: D

---

## Question 7: Request Logging Storage
Where should detailed request logs be stored?

A) Database only (same as usage data)
B) CloudWatch Logs only
C) Both Database and CloudWatch Logs
D) S3 for long-term storage + Database for recent queries
E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 8: Access Key Generation
How should Access Keys be generated?

A) Cryptographically secure random bytes (crypto.randomBytes)
B) UUID v4 with custom prefix
C) JWT-style signed tokens
D) Hash-based generation (HMAC)
E) Other (please describe after [Answer]: tag below)

[Answer]: An Access Key is generated as a URL-safe string (UUID v4) with the ak_ prefix, using at least 32 bytes of randomness (approximately 43–64 characters in length).

---

## Question 9: Bedrock Model Default
What should be the default Bedrock model if user doesn't specify?

A) anthropic.claude-3-5-sonnet-20241022-v2:0
B) anthropic.claude-3-5-sonnet-20240620-v1:0
C) anthropic.claude-3-opus-20240229-v1:0
D) anthropic.claude-3-haiku-20240307-v1:0
E) Other (please describe after [Answer]: tag below)

[Answer]: global.anthropic.claude-sonnet-4-5-20250929-v1:0

---

## Question 10: Bedrock Region Default
What should be the default Bedrock region if user doesn't specify?

A) us-east-1
B) us-west-2
C) ap-northeast-1 (Tokyo)
D) ap-northeast-2 (Seoul)
E) Other (please describe after [Answer]: tag below)

[Answer]: ap-northeast-2

---

## Question 11: Rate Limiting
Should the proxy implement rate limiting per Access Key?

A) Yes - limit requests per minute per Access Key
B) Yes - limit requests per hour per Access Key
C) Yes - both per-minute and per-hour limits
D) No - rely on upstream rate limits only
E) Other (please describe after [Answer]: tag below)

[Answer]: Not yet. However, a budget-based limit policy may be added in the future.

---

## Question 12: Admin Password Security
How should the admin password be managed?

A) Hardcoded default (admin/admin) - must change on first login
B) Environment variable only
C) Stored in AWS Secrets Manager
D) Stored in database with bcrypt hashing
E) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 13: Usage Data Retention
How long should raw request logs be retained?

A) 7 days (rely on aggregations for historical data)
B) 30 days
C) 90 days
D) 1 year
E) Other (please describe after [Answer]: tag below)

[Answer]: None. It has already been logged in the Bedrock Invocation Log.

---

## Question 14: Error Response Format
When both Plan and Bedrock fail, what error format should be returned?

A) Anthropic-compatible error format
B) Custom error format with detailed debugging info
C) Anthropic-compatible with additional custom fields
D) Standard HTTP error with JSON body
E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 15: Monitoring and Alerting
What monitoring should be implemented?

A) CloudWatch metrics only (latency, error rate, request count)
B) CloudWatch + SNS alerts for critical errors
C) CloudWatch + X-Ray for distributed tracing
D) Full observability stack (CloudWatch + X-Ray + SNS)
E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 16: Bedrock API Key Format
What format are the Bedrock API Keys that users will provide?

A) AWS IAM Access Key + Secret Key pair
B) Bearer token from Bedrock API
C) AWS STS temporary credentials
D) Cross-account IAM role ARN
E) Other (please describe after [Answer]: tag below)

[Answer]: The Bedrock API key must be issued using the AWS SDK or CLI.

---

## Question 17: Concurrent Request Handling
How should concurrent requests to the same Access Key be handled?

A) No special handling - process all concurrently
B) Queue requests per Access Key to prevent thundering herd
C) Limit concurrent requests per Access Key (e.g., max 5)
D) Use request deduplication for identical requests
E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 18: Health Check Endpoints
What health check endpoints should be exposed?

A) Simple /health endpoint (200 OK if service running)
B) /health with dependency checks (DB, Bedrock connectivity)
C) Separate /health and /ready endpoints (Kubernetes-style)
D) /health + /metrics (Prometheus-compatible)
E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 19: CORS Configuration
Should the proxy API support CORS for browser-based clients?

A) Yes - allow all origins
B) Yes - allow specific origins only (configurable)
C) No - server-to-server only
D) Yes - but only for Admin UI, not proxy API
E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 20: Deployment Environment
What AWS account/environment setup should be used?

A) Single AWS account for all environments
B) Separate AWS accounts for dev/staging/prod
C) Single account with separate VPCs per environment
D) Start with single account, plan for multi-account later
E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

**Instructions:**
1. Please answer each question by filling in the letter choice (A, B, C, D, or E) after the [Answer]: tag
2. If you choose "Other", please provide a brief description of your preference after the [Answer]: tag
3. Let me know when you've completed all answers so I can proceed with the analysis

