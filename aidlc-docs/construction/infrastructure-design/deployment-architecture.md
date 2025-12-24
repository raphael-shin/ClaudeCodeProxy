# Deployment Architecture - ClaudeCodeProxy

## Environment: Development (Single)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AWS Account (Dev)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         VPC (10.0.0.0/16)                            │    │
│  │                                                                      │    │
│  │  ┌──────────────────────┐    ┌──────────────────────┐               │    │
│  │  │   Public Subnet A    │    │   Public Subnet B    │               │    │
│  │  │    10.0.1.0/24       │    │    10.0.2.0/24       │               │    │
│  │  │                      │    │                      │               │    │
│  │  │  ┌──────────────┐    │    │                      │               │    │
│  │  │  │     ALB      │◄───┼────┼── Internet           │               │    │
│  │  │  │  (HTTPS:443) │    │    │                      │               │    │
│  │  │  └──────┬───────┘    │    │                      │               │    │
│  │  └─────────┼────────────┘    └──────────────────────┘               │    │
│  │            │                                                         │    │
│  │  ┌─────────┼────────────┐    ┌──────────────────────┐               │    │
│  │  │  Private│Subnet A    │    │   Private Subnet B   │               │    │
│  │  │   10.0.11.0/24       │    │    10.0.12.0/24      │               │    │
│  │  │         │            │    │                      │               │    │
│  │  │  ┌──────▼───────┐    │    │  ┌──────────────┐    │               │    │
│  │  │  │  ECS Task 1  │    │    │  │  ECS Task 2  │    │               │    │
│  │  │  │  (Fargate)   │    │    │  │  (Fargate)   │    │               │    │
│  │  │  └──────┬───────┘    │    │  └──────┬───────┘    │               │    │
│  │  │         │            │    │         │            │               │    │
│  │  │         └────────────┼────┼─────────┘            │               │    │
│  │  │                      │    │         │            │               │    │
│  │  │  ┌───────────────────┼────┼─────────▼──────────┐ │               │    │
│  │  │  │        Aurora PostgreSQL Serverless v2      │ │               │    │
│  │  │  │              (0.5 - 4 ACU)                  │ │               │    │
│  │  │  └─────────────────────────────────────────────┘ │               │    │
│  │  └──────────────────────┘    └──────────────────────┘               │    │
│  │                                                                      │    │
│  │  ┌─────────────┐                                                    │    │
│  │  │ NAT Gateway │ (AZ-a only for cost optimization)                  │    │
│  │  └─────────────┘                                                    │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Supporting Services                           │    │
│  │                                                                      │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │    │
│  │  │   Route 53  │  │     ACM     │  │  Secrets    │  │    KMS     │  │    │
│  │  │  (DNS)      │  │ (TLS Cert)  │  │  Manager    │  │ (CMK)      │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │    │
│  │                                                                      │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │    │
│  │  │ CloudWatch  │  │ CloudWatch  │  │ CloudWatch  │                  │    │
│  │  │   Logs      │  │  Metrics    │  │  Alarms     │                  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                  │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Resource Specifications

### Compute (Balanced)

| Resource | Specification | Notes |
|----------|---------------|-------|
| ECS Task CPU | 512 (0.5 vCPU) | Balanced for dev |
| ECS Task Memory | 1024 MB | Balanced for dev |
| Min Tasks | 2 | High availability |
| Max Tasks | 10 | Auto-scaling limit |
| CPU Scale Target | 70% | Scale out trigger |
| Memory Scale Target | 80% | Scale out trigger |

### Database (Balanced)

| Resource | Specification | Notes |
|----------|---------------|-------|
| Engine | Aurora PostgreSQL 15.4 | Serverless v2 |
| Min ACU | 0.5 | Cost optimization |
| Max ACU | 4 | Balanced capacity |
| Storage | Auto-scaling | Encrypted |
| Backup Retention | 7 days | Default policy |
| Multi-AZ | Yes | Writer in AZ-a |

### Networking

| Resource | Specification | Notes |
|----------|---------------|-------|
| VPC CIDR | 10.0.0.0/16 | 65,536 IPs |
| Public Subnets | 2 (AZ-a, AZ-b) | ALB placement |
| Private Subnets | 2 (AZ-a, AZ-b) | ECS, RDS placement |
| NAT Gateway | 1 (AZ-a only) | Cost optimization |
| Internet Gateway | 1 | Public access |

---

## DNS & Certificate

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Route 53     │────▶│       ALB       │────▶│   ECS Service   │
│                 │     │                 │     │                 │
│ proxy.example.com     │  HTTPS (443)    │     │  HTTP (8000)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │   ACM Cert      │
                        │ (DNS validated) │
                        └─────────────────┘
```

**Setup Steps**:
1. Register domain in Route 53 (or use existing)
2. CDK creates ACM certificate with DNS validation
3. CDK creates Route 53 validation records
4. CDK creates A record pointing to ALB

---

## Secrets Configuration

| Secret Name | Purpose | Rotation |
|-------------|---------|----------|
| claude-code-proxy/plan-api-key | Optional default Plan API key (not created by CDK) | Manual |
| claude-code-proxy/admin-credentials | Admin login (username/password) | Manual |
| claude-code-proxy/key-hasher-secret | HMAC server secret | Manual |
| (auto-generated) | Database credentials | Auto (RDS) |

---

## External Connections

```
┌─────────────────────────────────────────────────────────────────┐
│                        ECS Tasks                                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
    ┌───────────────┐ ┌───────────┐ ┌───────────────┐
    │ Anthropic API │ │  Bedrock  │ │  CloudWatch   │
    │ (Plan)        │ │ Converse │ │  API          │
    │               │ │           │ │               │
    │ api.anthropic │ │ bedrock.  │ │ monitoring.   │
    │ .com          │ │ region.   │ │ region.       │
    │               │ │ amazonaws │ │ amazonaws.com │
    └───────────────┘ └───────────┘ └───────────────┘
         HTTPS            HTTPS          HTTPS
       (via NAT)      (via NAT)      (via NAT)
```

---

## Cost Estimate (Monthly, Dev Environment)

| Service | Specification | Est. Cost |
|---------|---------------|-----------|
| ECS Fargate | 2 tasks × 0.5 vCPU × 1GB × 730h | ~$30 |
| Aurora Serverless v2 | 0.5-4 ACU (avg 1 ACU) | ~$45 |
| ALB | 1 ALB + LCU | ~$20 |
| NAT Gateway | 1 gateway + data | ~$35 |
| Route 53 | 1 hosted zone | ~$0.50 |
| Secrets Manager | 4 secrets | ~$2 |
| CloudWatch | Logs + Metrics | ~$10 |
| **Total** | | **~$145/month** |

*Note: Actual costs vary based on usage. Bedrock API costs are separate.*

---

## Deployment Workflow

```
Developer Machine
       │
       │ cdk deploy --all
       ▼
┌─────────────────┐
│  CloudFormation │
│                 │
│  1. NetworkStack│
│  2. SecretsStack│
│  3. DatabaseStack│
│  4. ComputeStack│
│  5. MonitoringStack│
└─────────────────┘
       │
       ▼
   AWS Resources
    Provisioned
```

**Manual Steps After Deployment**:
1. (Optional) Set Plan API key in Secrets Manager if you want a default key
2. Configure domain DNS (if not using Route 53)
3. Run database migrations
4. Verify health check endpoint
