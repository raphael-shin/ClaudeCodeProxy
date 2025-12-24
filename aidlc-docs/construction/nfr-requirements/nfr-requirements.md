# NFR Requirements - ClaudeCodeProxy

## Performance Requirements

### Latency SLOs

| Path | Metric | Target | Description |
|------|--------|--------|-------------|
| Plan-only | p95 | < 100ms | Proxy overhead for Plan upstream |
| Bedrock fallback | p95 | < 500ms | Including transformation overhead |
| Admin API | p95 | < 200ms | Admin operations |
| Admin UI | p95 | < 1s | Page load time |

### Throughput

| Metric | Target | Notes |
|--------|--------|-------|
| Request volume | 100-1000 req/min | Launch target |
| Concurrent connections | 100+ | Per ECS task |
| Database connections | 5-10 per instance | Connection pool size |

### Resource Limits

| Resource | Limit | Notes |
|----------|-------|-------|
| Request body size | 10MB | Anthropic API limit |
| Response timeout | 5 minutes | Long-running completions |
| Connection timeout | 5 seconds | Upstream connection |

---

## Availability Requirements

### Uptime SLA

| Metric | Target | Allowed Downtime |
|--------|--------|------------------|
| Monthly uptime | 99.9% | ~44 minutes/month |
| Planned maintenance | Excluded | Rolling deployments |

### Redundancy

| Component | Configuration | Notes |
|-----------|---------------|-------|
| ECS Tasks | Minimum 2 | Multi-AZ deployment |
| Aurora | Multi-AZ | Automatic failover |
| ALB | Multi-AZ | AWS managed |

### Failure Handling

| Scenario | Behavior |
|----------|----------|
| Single task failure | ALB routes to healthy task |
| Plan upstream down | Automatic Bedrock fallback |
| Bedrock down | Return error with request_id |
| Database failover | ~30 second interruption |

---

## Security Requirements

### Data Protection

| Data Type | At Rest | In Transit |
|-----------|---------|------------|
| Bedrock API Keys | KMS envelope encryption | TLS 1.2+ |
| Access Key hashes | Database encryption | TLS 1.2+ |
| Request/Response | Not stored | TLS 1.2+ |
| Admin credentials | Secrets Manager | TLS 1.2+ |

### Access Control

| Component | Control | Notes |
|-----------|---------|-------|
| Proxy API | Access Key in URL | No auth header |
| Admin UI | IP allowlist + auth | Restricted access |
| Admin API | JWT session token | 24-hour expiry |
| AWS Resources | IAM roles | Least privilege |

### TLS Configuration

| Setting | Value |
|---------|-------|
| Minimum version | TLS 1.2 |
| Certificate | AWS ACM managed |
| HTTPS redirect | Enabled |
| HSTS | Enabled |

### Key Security

| Key Type | Storage | Display |
|----------|---------|---------|
| Access Key | HMAC hash + prefix | Prefix only after creation |
| Bedrock Key | KMS encrypted | Never displayed |
| Admin password | bcrypt hash (prod) | Never displayed |
| Server secret | Secrets Manager | Never displayed |

---

## Scalability Requirements

### Auto-Scaling

| Metric | Scale Out | Scale In | Limits |
|--------|-----------|----------|--------|
| CPU | > 70% for 3 min | < 30% for 10 min | 2-10 tasks |
| Memory | > 80% for 3 min | < 40% for 10 min | 2-10 tasks |

### Database Scaling

| Setting | Value | Notes |
|---------|-------|-------|
| Aurora capacity | 0.5-4 ACU | Serverless v2 |
| Auto-pause | Disabled | Always available |
| Read replicas | 0 (MVP) | Add if needed |

### Limits

| Resource | Soft Limit | Hard Limit |
|----------|------------|------------|
| Users | 1000 | Configurable |
| Access Keys per user | 10 | Configurable |
| Requests per minute | 1000 | Auto-scale |

---

## Observability Requirements

### Logging

| Log Type | Destination | Retention |
|----------|-------------|-----------|
| Application logs | CloudWatch Logs | 30 days |
| Access logs | CloudWatch Logs | 30 days |
| Error logs | CloudWatch Logs | 30 days |

### Log Format

```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "level": "INFO",
  "request_id": "req_...",
  "message": "...",
  "context": {
    "user_id": "...",
    "access_key_id": "...",
    "provider": "plan|bedrock"
  }
}
```

### Metrics

| Metric | Dimensions | Unit |
|--------|------------|------|
| RequestCount | provider | Count |
| RequestLatency | provider | Milliseconds |
| ErrorCount | error_type | Count |
| FallbackCount | - | Count |
| CircuitBreakerState | access_key_id | Count |
| TokensUsed | token_type | Count |

### Alerting

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Error Rate | > 1% over 5 min | Critical |
| High Latency | p95 > 1s over 5 min | Warning |
| Task Unhealthy | < 2 healthy tasks | Critical |
| Database CPU | > 80% over 5 min | Warning |
| Circuit Breaker Open | Any key open | Info |

---

## Compliance Requirements

### Data Handling

| Requirement | Implementation |
|-------------|----------------|
| No PII logging | Mask user data in logs |
| Key masking | Never log full keys |
| Request body | Not stored |
| Audit trail | Request logs retained 30 days |

### AWS Best Practices

| Practice | Implementation |
|----------|----------------|
| Least privilege | IAM roles per service |
| Encryption | KMS for sensitive data |
| Network isolation | Private subnets for ECS |
| Secrets management | AWS Secrets Manager |
