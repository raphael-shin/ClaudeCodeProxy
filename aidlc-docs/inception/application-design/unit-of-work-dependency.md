# Unit of Work Dependencies - ClaudeCodeProxy

## Development Phases (Risk-First Hybrid)

```
Phase 1: Foundation (Parallel)
├── Shared (core types, config, repo interfaces)
└── Infra-A (VPC, Aurora, KMS, Secrets)

Phase 2: Proxy Core Path (Vertical Slice)
├── 1A (Ingress & Auth)
├── 1B (Plan Adapter)
└── 1D (Router - Plan only)
    Goal: Plan-only success path E2E

Phase 3: Bedrock Fallback
├── 1C (Bedrock Adapter)
└── 1D (Router - extend with fallback + circuit breaker)

Phase 4: Observability
└── 1E (Usage Metering)

Phase 5: Admin
├── 2 (Admin Backend)
└── 3 (Admin Frontend)

Phase 6: Production Readiness
└── Infra-B (ECS wiring, autoscaling, alarms)
```

---

## Dependency Matrix

### Build-Time Dependencies

| Unit | Depends On | Notes |
|------|------------|-------|
| Shared | - | Foundation, no dependencies |
| 1A | Shared | Types, repositories, cache |
| 1B | Shared | Types, config |
| 1C | Shared | Types, BedrockKeyService |
| 1D | Shared, 1B, 1C | Adapter protocols |
| 1E | Shared | Repositories, metrics |
| 2 | Shared | All services |
| 3 | - | Standalone Next.js |
| 4 | - | Standalone CDK |

### Runtime Dependencies

| Unit | Runtime Dependencies |
|------|---------------------|
| Shared | Database, Secrets Manager, KMS |
| 1A | Database (via Shared) |
| 1B | Anthropic API |
| 1C | Bedrock Runtime API, KMS |
| 1D | 1B, 1C (injected) |
| 1E | Database, CloudWatch |
| 2 | Database, Secrets Manager, KMS |
| 3 | Unit 2 API |
| 4 | AWS APIs |

---

## Integration Points

### 1A ↔ 1D (RequestContext)

```python
# Contract: 1A produces, 1D consumes
@dataclass
class RequestContext:
    request_id: str
    user_id: str
    access_key_id: str
    bedrock_region: str
    bedrock_model: str
    has_bedrock_key: bool
    received_at: datetime
```

### 1B/1C ↔ 1D (UpstreamAdapter Protocol)

```python
# Contract: 1B and 1C implement, 1D consumes
class UpstreamAdapter(Protocol):
    async def invoke(
        self, 
        ctx: RequestContext, 
        request: AnthropicRequest
    ) -> AdapterResponse | AdapterError:
        ...
```

### 1D ↔ 1E (ProxyResponse)

```python
# Contract: 1D produces, 1E consumes
@dataclass
class ProxyResponse:
    is_success: bool
    provider: str  # "plan" | "bedrock"
    is_fallback: bool
    status_code: int
    error_type: str | None
    response: AdapterResponse | None
```

### 2 ↔ 3 (REST API)

```yaml
# Contract: OpenAPI schema
openapi: 3.0.0
paths:
  /admin/users:
    get: { ... }
    post: { ... }
  /admin/access-keys/{id}:
    delete: { ... }
  # ... etc
```

---

## Critical Path

```
Shared → 1A → 1B → 1D(minimal) → [Plan-only E2E milestone]
                ↓
              1C → 1D(full) → 1E → [Proxy complete milestone]
                                ↓
                              2 → 3 → [Admin complete milestone]
```

### Milestones

| Milestone | Units Complete | Deliverable |
|-----------|----------------|-------------|
| M1: Plan-only E2E | Shared, 1A, 1B, 1D(minimal) | Proxy works with Plan upstream only |
| M2: Proxy Complete | + 1C, 1D(full), 1E | Full proxy with fallback and metering |
| M3: Admin Complete | + 2, 3 | Full admin UI and API |
| M4: Production Ready | + Infra-B | Deployed to AWS |

---

## Parallelization Opportunities

### Phase 1 (Can run in parallel)
- Shared foundation
- Infra-A (VPC, Aurora, KMS)

### Phase 2-3 (Limited parallelism)
- 1B and 1C can be developed in parallel after 1A
- 1D depends on 1B/1C interfaces (can start with mocks)

### Phase 5 (Can run in parallel)
- Unit 2 and Unit 3 can be developed in parallel
- Unit 3 can use mock API initially

---

## Contract Testing Strategy

| Contract | Producer | Consumer | Test Type |
|----------|----------|----------|-----------|
| RequestContext | 1A | 1D | Schema validation |
| UpstreamAdapter | 1B, 1C | 1D | Protocol compliance |
| AdapterResponse | 1B, 1C | 1D, 1E | Schema validation |
| ProxyResponse | 1D | 1E | Schema validation |
| Admin API | 2 | 3 | OpenAPI contract |

### Contract Test Implementation

```python
# Example: UpstreamAdapter contract test
def test_plan_adapter_implements_protocol():
    adapter = PlanAdapter(api_key="test")
    assert isinstance(adapter, UpstreamAdapter)

def test_adapter_response_schema():
    response = AdapterResponse(...)
    # Validate all required fields present
    assert response.content is not None
    assert isinstance(response.usage, TokenUsage)
```

---

## Database Schema Dependencies

### Migration Order

```
1. users table
2. access_keys table (FK: users)
3. bedrock_keys table (FK: access_keys)
4. request_logs table (FK: users, access_keys)
5. token_usage table (FK: users, access_keys)
6. usage_aggregates table (FK: users, access_keys)
```

### Schema Ownership

| Table | Owner | Used By |
|-------|-------|---------|
| users | Shared | 1A, 2 |
| access_keys | Shared | 1A, 2 |
| bedrock_keys | Shared | 1C, 2 |
| request_logs | Shared | 1E, 2 |
| token_usage | Shared | 1E, 2 |
| usage_aggregates | Shared | 2 |

---

## Risk Mitigation

### High-Risk Dependencies

| Risk | Mitigation |
|------|------------|
| Bedrock API changes | Contract tests, version pinning |
| KMS latency | TTL cache for decrypted keys |
| Database bottleneck | Connection pooling, read replicas (future) |
| Circuit breaker state loss | In-memory acceptable for MVP, Redis for scale |

### Dependency Isolation

- Each unit can be tested with mocks
- Protocol-based adapters enable substitution
- Shared module provides stable interfaces
