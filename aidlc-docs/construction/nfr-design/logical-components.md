# Logical Components - ClaudeCodeProxy

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Internet                                    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Application Load Balancer                         │
│                    (TLS termination, health checks)                      │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
          ┌─────────────────┐         ┌─────────────────┐
          │   ECS Task 1    │         │   ECS Task 2    │
          │  (Proxy+Admin)  │         │  (Proxy+Admin)  │
          └────────┬────────┘         └────────┬────────┘
                   │                           │
                   └─────────────┬─────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │ Aurora Postgres │ │ Secrets Manager │ │      KMS        │
    │  Serverless v2  │ │                 │ │                 │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## Compute Layer

### ECS Fargate Service

**Configuration**:
```yaml
Service:
  name: claude-code-proxy
  launch_type: FARGATE
  desired_count: 2
  
Task:
  cpu: 512 (0.5 vCPU)
  memory: 1024 (1 GB)
  
Container:
  name: proxy
  port: 8000
  health_check: /health
  
Auto-Scaling:
  min: 2
  max: 10
  cpu_target: 70%
  memory_target: 80%
```

**Health Check**:
```python
@app.get("/health")
async def health():
    return {"status": "healthy"}
```

---

### Application Load Balancer

**Configuration**:
```yaml
ALB:
  scheme: internet-facing
  
Listeners:
  - port: 443
    protocol: HTTPS
    certificate: ACM
    default_action: forward to target_group
  - port: 80
    protocol: HTTP
    default_action: redirect to HTTPS

Target Group:
  protocol: HTTP
  port: 8000
  health_check:
    path: /health
    interval: 30s
    timeout: 5s
    healthy_threshold: 2
    unhealthy_threshold: 3
```

**Path Routing**:
```yaml
Rules:
  - path: /ak/*
    target: proxy_target_group
  - path: /admin/*
    target: proxy_target_group
    conditions:
      - source_ip: [allowed_ips]
```

---

## Data Layer

### Aurora PostgreSQL Serverless v2

**Configuration**:
```yaml
Cluster:
  engine: aurora-postgresql
  engine_version: "15.4"
  serverless_v2_scaling:
    min_capacity: 0.5
    max_capacity: 4
  
Instance:
  instance_class: db.serverless
  multi_az: true
  
Storage:
  encrypted: true
  kms_key: customer_managed
  
Backup:
  retention_period: 7 days
  preferred_window: "03:00-04:00"
```

**Connection String**:
```
postgresql+asyncpg://{user}:{password}@{host}:5432/{database}?ssl=require
```

---

### Database Schema

**설계 원칙**:
- PostgreSQL에는 Bedrock token_usage만 저장
- 요청 로그/디버깅은 CloudWatch Logs로 해결 (request_id 기반 조회)

```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Access keys table
CREATE TABLE access_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    key_prefix VARCHAR(12) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    bedrock_region VARCHAR(32) NOT NULL DEFAULT 'ap-northeast-2',
    bedrock_model VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    rotation_expires_at TIMESTAMPTZ
);

-- Bedrock keys table
CREATE TABLE bedrock_keys (
    access_key_id UUID PRIMARY KEY REFERENCES access_keys(id),
    encrypted_key BYTEA NOT NULL,
    key_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rotated_at TIMESTAMPTZ
);

-- Token usage table (Bedrock only - 단일 소스)
CREATE TABLE token_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(64) NOT NULL UNIQUE,
    timestamp TIMESTAMPTZ NOT NULL,
    user_id UUID NOT NULL,
    access_key_id UUID NOT NULL,
    -- 사용량
    model VARCHAR(128) NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_read_input_tokens INTEGER,
    cache_creation_input_tokens INTEGER,
    total_tokens INTEGER NOT NULL,
    -- 라우팅/분석
    provider VARCHAR(10) NOT NULL DEFAULT 'bedrock',
    is_fallback BOOLEAN NOT NULL DEFAULT FALSE,
    latency_ms INTEGER NOT NULL
);

-- Usage aggregates table
CREATE TABLE usage_aggregates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bucket_type VARCHAR(10) NOT NULL,
    bucket_start TIMESTAMPTZ NOT NULL,
    user_id UUID NOT NULL,
    access_key_id UUID,
    total_requests INTEGER NOT NULL DEFAULT 0,
    total_input_tokens BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    UNIQUE(bucket_type, bucket_start, user_id, access_key_id)
);

-- Indexes
CREATE INDEX idx_access_keys_user_id ON access_keys(user_id);
CREATE INDEX idx_access_keys_key_hash ON access_keys(key_hash);
CREATE INDEX idx_token_usage_timestamp ON token_usage(timestamp);
CREATE INDEX idx_token_usage_user_timestamp ON token_usage(user_id, timestamp);
CREATE INDEX idx_token_usage_access_key_timestamp ON token_usage(access_key_id, timestamp);
CREATE INDEX idx_usage_aggregates_lookup ON usage_aggregates(bucket_type, bucket_start, user_id);
```

---

## Security Layer

### AWS Secrets Manager

**Secrets**:
```yaml
Secrets:
  - name: claude-code-proxy/plan-api-key
    description: Optional default Plan API key (not created by CDK)
    
  - name: claude-code-proxy/admin-credentials
    description: Admin username and password hash
    
  - name: claude-code-proxy/key-hasher-secret
    description: Server secret for HMAC hashing
    
  - name: claude-code-proxy/database
    description: Database connection credentials
```

---

### AWS KMS

**Key Configuration**:
```yaml
KMS Key:
  alias: alias/claude-code-proxy
  description: Encryption key for Bedrock API keys
  key_spec: SYMMETRIC_DEFAULT
  key_usage: ENCRYPT_DECRYPT
  
Policy:
  - Allow ECS task role to Encrypt/Decrypt
  - Allow admin role to manage key
```

---

## Networking Layer

### VPC Configuration

```yaml
VPC:
  cidr: 10.0.0.0/16
  
Subnets:
  public:
    - 10.0.1.0/24 (AZ-a)
    - 10.0.2.0/24 (AZ-b)
  private:
    - 10.0.11.0/24 (AZ-a)
    - 10.0.12.0/24 (AZ-b)

NAT Gateway:
  - AZ-a (for private subnet egress)

Internet Gateway:
  - Attached to VPC
```

---

### Security Groups

```yaml
ALB Security Group:
  inbound:
    - port: 443, source: 0.0.0.0/0
    - port: 80, source: 0.0.0.0/0
  outbound:
    - all traffic

ECS Security Group:
  inbound:
    - port: 8000, source: ALB_SG
  outbound:
    - all traffic

Database Security Group:
  inbound:
    - port: 5432, source: ECS_SG
  outbound:
    - none
```

---

## Observability Layer

### CloudWatch Logs

**Log Groups**:
```yaml
Log Groups:
  - /ecs/claude-code-proxy
    retention: 30 days
    
  - /aws/rds/cluster/claude-code-proxy
    retention: 30 days
```

---

### CloudWatch Metrics

**Custom Metrics Namespace**: `ClaudeCodeProxy`

**Metrics**:
```yaml
Metrics:
  - RequestCount (Provider=plan/bedrock)
  - RequestLatency (Provider=plan/bedrock)
  - ErrorCount (ErrorType, Provider)
  - FallbackCount
  - CircuitOpen
  - BedrockTokensUsed (TokenType=input/output)
```

---

### CloudWatch Alarms

**알람 설계 원칙**:
- Provider dimension으로 분리
- 최소 트래픽 조건 추가 (노이즈 방지)

```yaml
Alarms:
  - name: HighErrorRate-Plan
    metric: ErrorCount (Provider=plan) / RequestCount (Provider=plan)
    threshold: 5%
    period: 5 minutes
    datapoints: 3 of 5
    condition: RequestCount >= 10  # 최소 트래픽
    action: SNS notification
    
  - name: HighErrorRate-Bedrock
    metric: ErrorCount (Provider=bedrock) / RequestCount (Provider=bedrock)
    threshold: 1%
    period: 5 minutes
    datapoints: 3 of 5
    condition: RequestCount >= 10
    action: SNS notification
    
  - name: HighLatency-Plan
    metric: RequestLatency p95 (Provider=plan)
    threshold: 500ms
    period: 5 minutes
    condition: RequestCount >= 10
    action: SNS notification
    
  - name: HighLatency-Bedrock
    metric: RequestLatency p95 (Provider=bedrock)
    threshold: 1000ms
    period: 5 minutes
    condition: RequestCount >= 10
    action: SNS notification
    
  - name: HighFallbackRate
    metric: FallbackCount / RequestCount
    threshold: 10%
    period: 5 minutes
    condition: RequestCount >= 10
    action: SNS notification
    
  - name: UnhealthyTasks
    metric: HealthyHostCount
    threshold: < 2
    period: 1 minute
    action: SNS notification (critical)
```

---

## Component Summary

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| Load Balancer | ALB | Traffic distribution, TLS |
| Compute | ECS Fargate | Application hosting |
| Database | Aurora Serverless v2 | Data persistence |
| Secrets | Secrets Manager | Credential storage |
| Encryption | KMS | Key encryption |
| Networking | VPC | Network isolation |
| Logging | CloudWatch Logs | Application logs |
| Metrics | CloudWatch Metrics | Monitoring |
| Alerting | CloudWatch Alarms | Incident detection |
| Certificates | ACM | TLS certificates |
