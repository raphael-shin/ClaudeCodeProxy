# Unit of Work Story Map - ClaudeCodeProxy

## Story to Unit Mapping

| Story ID | Story Title | Primary Unit | Supporting Units |
|----------|-------------|--------------|------------------|
| US-1.1 | Admin Login | 2 | 3 |
| US-2.1 | Create New User | 2 | 3 |
| US-2.2 | Issue Access Key for User | 2 | 3, Shared |
| US-2.3 | Register Bedrock API Key | 2 | 3, Shared |
| US-2.4 | Configure Bedrock Settings | 2 | 3 |
| US-2.5 | Share Access Key with Developer | 2 | 3 |
| US-3.1 | Configure Claude Code with Proxy | 1A | - |
| US-3.2 | Make API Request via Proxy | 1A, 1B, 1D | 1E |
| US-3.3 | Automatic Failover to Bedrock | 1C, 1D | 1E |
| US-3.4 | Handle Invalid Access Key | 1A | - |
| US-3.5 | Handle Complete Failure | 1D | 1E |
| US-4.1 | View Usage Dashboard | 2 | 3, 1E |
| US-4.2 | View Usage by User | 2 | 3, 1E |
| US-5.1 | View All Users | 2 | 3 |
| US-5.2 | Deactivate User | 2 | 3, Shared |
| US-5.3 | Revoke Access Key | 2 | 3, Shared |
| US-5.4 | Rotate Access Key | 2 | 3, Shared |
| US-5.5 | Rotate Bedrock API Key | 2 | 3, Shared |
| US-6.1 | Check System Health | 1A | 4 |
| US-6.2 | Monitor Circuit Breaker Status | 1D | 1E, 4 |

---

## Unit to Story Mapping

### Unit 1A: Request Ingress & Auth

| Story ID | Story Title | Role |
|----------|-------------|------|
| US-3.1 | Configure Claude Code with Proxy | Primary |
| US-3.2 | Make API Request via Proxy | Primary |
| US-3.4 | Handle Invalid Access Key | Primary |
| US-6.1 | Check System Health | Primary |

**Coverage**: 4 stories

---

### Unit 1B: Plan Upstream Adapter

| Story ID | Story Title | Role |
|----------|-------------|------|
| US-3.2 | Make API Request via Proxy | Primary |

**Coverage**: 1 story (core functionality)

---

### Unit 1C: Bedrock Adapter

| Story ID | Story Title | Role |
|----------|-------------|------|
| US-3.3 | Automatic Failover to Bedrock | Primary |

**Coverage**: 1 story (core functionality)

---

### Unit 1D: Routing & Circuit Breaker

| Story ID | Story Title | Role |
|----------|-------------|------|
| US-3.2 | Make API Request via Proxy | Primary |
| US-3.3 | Automatic Failover to Bedrock | Primary |
| US-3.5 | Handle Complete Failure | Primary |
| US-6.2 | Monitor Circuit Breaker Status | Primary |

**Coverage**: 4 stories

---

### Unit 1E: Usage Metering & Observability

| Story ID | Story Title | Role |
|----------|-------------|------|
| US-3.2 | Make API Request via Proxy | Supporting |
| US-3.3 | Automatic Failover to Bedrock | Supporting |
| US-3.5 | Handle Complete Failure | Supporting |
| US-4.1 | View Usage Dashboard | Supporting |
| US-4.2 | View Usage by User | Supporting |
| US-6.2 | Monitor Circuit Breaker Status | Supporting |

**Coverage**: 6 stories (supporting role)

---

### Unit 2: Admin Backend

| Story ID | Story Title | Role |
|----------|-------------|------|
| US-1.1 | Admin Login | Primary |
| US-2.1 | Create New User | Primary |
| US-2.2 | Issue Access Key for User | Primary |
| US-2.3 | Register Bedrock API Key | Primary |
| US-2.4 | Configure Bedrock Settings | Primary |
| US-2.5 | Share Access Key with Developer | Primary |
| US-4.1 | View Usage Dashboard | Primary |
| US-4.2 | View Usage by User | Primary |
| US-5.1 | View All Users | Primary |
| US-5.2 | Deactivate User | Primary |
| US-5.3 | Revoke Access Key | Primary |
| US-5.4 | Rotate Access Key | Primary |
| US-5.5 | Rotate Bedrock API Key | Primary |

**Coverage**: 13 stories

---

### Unit 3: Admin Frontend

| Story ID | Story Title | Role |
|----------|-------------|------|
| US-1.1 | Admin Login | Supporting |
| US-2.1 | Create New User | Supporting |
| US-2.2 | Issue Access Key for User | Supporting |
| US-2.3 | Register Bedrock API Key | Supporting |
| US-2.4 | Configure Bedrock Settings | Supporting |
| US-2.5 | Share Access Key with Developer | Supporting |
| US-4.1 | View Usage Dashboard | Supporting |
| US-4.2 | View Usage by User | Supporting |
| US-5.1 | View All Users | Supporting |
| US-5.2 | Deactivate User | Supporting |
| US-5.3 | Revoke Access Key | Supporting |
| US-5.4 | Rotate Access Key | Supporting |
| US-5.5 | Rotate Bedrock API Key | Supporting |

**Coverage**: 13 stories (UI for Admin Backend)

---

### Unit 4: Infrastructure

| Story ID | Story Title | Role |
|----------|-------------|------|
| US-6.1 | Check System Health | Supporting |
| US-6.2 | Monitor Circuit Breaker Status | Supporting |

**Coverage**: 2 stories (supporting role)

---

### Shared Foundation

| Story ID | Story Title | Role |
|----------|-------------|------|
| US-2.2 | Issue Access Key for User | Supporting |
| US-2.3 | Register Bedrock API Key | Supporting |
| US-5.2 | Deactivate User | Supporting |
| US-5.3 | Revoke Access Key | Supporting |
| US-5.4 | Rotate Access Key | Supporting |
| US-5.5 | Rotate Bedrock API Key | Supporting |

**Coverage**: 6 stories (data layer support)

---

## Coverage Summary

| Unit | Primary Stories | Supporting Stories | Total |
|------|-----------------|-------------------|-------|
| 1A | 4 | 0 | 4 |
| 1B | 1 | 0 | 1 |
| 1C | 1 | 0 | 1 |
| 1D | 4 | 0 | 4 |
| 1E | 0 | 6 | 6 |
| 2 | 13 | 0 | 13 |
| 3 | 0 | 13 | 13 |
| 4 | 0 | 2 | 2 |
| Shared | 0 | 6 | 6 |

**Total Stories**: 20
**All Stories Assigned**: ✅ Yes

---

## Story Journey Coverage

### Journey 1: Admin Onboarding (1 story)
- US-1.1 → Unit 2, 3

### Journey 2: Developer Onboarding (5 stories)
- US-2.1 → Unit 2, 3
- US-2.2 → Unit 2, 3, Shared
- US-2.3 → Unit 2, 3, Shared
- US-2.4 → Unit 2, 3
- US-2.5 → Unit 2, 3

### Journey 3: Developer Using Proxy (5 stories)
- US-3.1 → Unit 1A
- US-3.2 → Unit 1A, 1B, 1D, 1E
- US-3.3 → Unit 1C, 1D, 1E
- US-3.4 → Unit 1A
- US-3.5 → Unit 1D, 1E

### Journey 4: Usage Monitoring (2 stories)
- US-4.1 → Unit 2, 3, 1E
- US-4.2 → Unit 2, 3, 1E

### Journey 5: Access Management (5 stories)
- US-5.1 → Unit 2, 3
- US-5.2 → Unit 2, 3, Shared
- US-5.3 → Unit 2, 3, Shared
- US-5.4 → Unit 2, 3, Shared
- US-5.5 → Unit 2, 3, Shared

### Journey 6: System Health (2 stories)
- US-6.1 → Unit 1A, 4
- US-6.2 → Unit 1D, 1E, 4

---

## Acceptance Test Mapping

| Story | Unit Tests | Contract Tests | Integration Tests |
|-------|------------|----------------|-------------------|
| US-1.1 | Unit 2 | API schema | Full login flow |
| US-2.1 | Unit 2 | API schema | User creation E2E |
| US-2.2 | Unit 2, Shared | Key format | Key issuance E2E |
| US-2.3 | Unit 2, Shared | Encryption | Key registration E2E |
| US-3.1 | Unit 1A | Context schema | Proxy config E2E |
| US-3.2 | Unit 1A, 1B, 1D | Adapter protocol | Plan request E2E |
| US-3.3 | Unit 1C, 1D | Adapter protocol | Fallback E2E |
| US-3.4 | Unit 1A | Error format | Invalid key E2E |
| US-3.5 | Unit 1D | Error format | Failure E2E |
| US-4.1 | Unit 2, 1E | Usage schema | Dashboard E2E |
| US-6.2 | Unit 1D | Metrics schema | Circuit breaker E2E |
