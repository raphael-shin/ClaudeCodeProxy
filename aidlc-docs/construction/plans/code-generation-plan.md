# Code Generation Plan - ClaudeCodeProxy

## Overview
전체 시스템 코드 생성 계획. Shared Foundation부터 시작하여 순차적으로 진행.

## Generation Order
1. Shared Foundation (공통 모듈)
2. Unit 1A-1E (Proxy Core)
3. Unit 2 (Admin Backend)
4. Unit 3 (Admin Frontend)
5. Unit 4 (Infrastructure CDK)

---

## Phase 1: Shared Foundation

### Step 1.1: Project Structure & Configuration
- [x] Create Python project structure (pyproject.toml, src layout)
- [x] Create configuration module (settings, environment loading)
- [x] Create logging setup (structlog with JSON output)

### Step 1.2: Core Types & Models
- [x] Create domain entities (User, AccessKey, BedrockKey, TokenUsage, UsageAggregate)
- [x] Create Pydantic schemas for API request/response
- [x] Create error types and enums (ErrorType, UserStatus, KeyStatus)

### Step 1.3: Database Layer
- [x] Create SQLAlchemy models
- [x] Create Alembic migration setup
- [x] Create initial migration (all tables)
- [x] Create async session factory

### Step 1.4: Repository Layer
- [x] Create UserRepository
- [x] Create AccessKeyRepository
- [x] Create BedrockKeyRepository
- [x] Create TokenUsageRepository
- [x] Create UsageAggregateRepository

### Step 1.5: Security Utilities
- [x] Create KeyHasher (HMAC-SHA256)
- [x] Create KeyGenerator (secure random)
- [x] Create KeyMasker (prefix display)
- [x] Create KMSEnvelopeEncryption

---

## Phase 2: Proxy Core (Units 1A-1E)

### Step 2.1: Unit 1A - Request Ingress
- [x] Create FastAPI app entry point
- [x] Create proxy router (/ak/{access_key}/v1/messages)
- [x] Create AccessKeyCache (in-memory TTL)
- [x] Create authentication middleware
- [x] Create RequestContext builder

### Step 2.2: Unit 1B - Plan Adapter
- [x] Create PlanAdapter class
- [x] Create Anthropic request/response models
- [x] Create error classification logic
- [x] Create HTTP client with timeouts

### Step 2.3: Unit 1C - Bedrock Adapter
- [x] Create BedrockAdapter class
- [x] Create Anthropic↔Bedrock request transformer
- [x] Create Bedrock↔Anthropic response transformer
- [x] Create BedrockKeyCache (decrypted key TTL)
- [x] Create BedrockKeyService

### Step 2.4: Unit 1D - Router & Circuit Breaker
- [x] Create CircuitBreaker class (per-key state)
- [x] Create ProxyRouter (routing logic)
- [x] Create fallback policy implementation

### Step 2.5: Unit 1E - Usage Metering
- [x] Create UsageRecorder (async background)
- [x] Create MetricsEmitter (CloudWatch)
- [x] Create structured logging for requests

---

## Phase 3: Admin Backend (Unit 2)

### Step 3.1: Admin Authentication
- [x] Create admin auth router (/admin/auth)
- [x] Create JWT session management
- [x] Create admin credentials validation

### Step 3.2: User Management API
- [x] Create user router (/admin/users)
- [x] Create UserService
- [x] Implement CRUD operations

### Step 3.3: Access Key Management API
- [x] Create access key endpoints
- [x] Create AccessKeyService
- [x] Implement issue, revoke, rotate operations

### Step 3.4: Bedrock Key Management API
- [x] Create bedrock key endpoints
- [x] Implement register, rotate operations

### Step 3.5: Usage Dashboard API
- [x] Create usage router (/admin/usage)
- [x] Create UsageService
- [x] Implement aggregation queries

---

## Phase 4: Admin Frontend (Unit 3)

### Step 4.1: Next.js Project Setup
- [x] Create Next.js 14 project (App Router)
- [x] Configure Tailwind CSS
- [x] Create API client utility

### Step 4.2: Authentication Pages
- [x] Create login page
- [x] Create auth context/provider
- [x] Create protected route wrapper

### Step 4.3: User Management Pages
- [x] Create users list page
- [x] Create user detail page
- [x] Create user form components

### Step 4.4: Access Key Management UI
- [x] Create access key list component
- [x] Create key issue/revoke/rotate dialogs
- [x] Create bedrock key registration form

### Step 4.5: Usage Dashboard
- [x] Create usage dashboard page
- [x] Create usage charts (token usage over time)
- [x] Create usage filters (date range, user, key)

---

## Phase 5: Infrastructure (Unit 4)

### Step 5.1: CDK Project Setup
- [x] Create CDK Python project
- [x] Create stack structure

### Step 5.2: Foundation Stacks
- [x] Create NetworkStack (VPC, subnets, security groups)
- [x] Create SecretsStack (KMS, Secrets Manager)
- [x] Create DatabaseStack (Aurora Serverless v2)

### Step 5.3: Service Stacks
- [x] Create ComputeStack (ECS Fargate, ALB, ACM)
- [x] Create MonitoringStack (CloudWatch dashboards, alarms)

### Step 5.4: Deployment Configuration
- [x] Create Dockerfile for backend
- [x] Create docker-compose for local development
- [x] Create deployment scripts

---

## Completion Criteria
- [x] All phases completed
- [x] All code compiles/lints without errors
- [x] Project structure is consistent
- [x] README with setup instructions created
