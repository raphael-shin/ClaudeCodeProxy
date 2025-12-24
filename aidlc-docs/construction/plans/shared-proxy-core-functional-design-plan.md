# Functional Design Plan - Shared Foundation & Proxy Core

## Overview
This plan covers functional design for the foundation layer and proxy core units (Phase 1-2 of development).

**Units Covered:**
- Shared Foundation (core types, domain entities, business rules)
- Unit 1A: Request Ingress & Auth
- Unit 1B: Plan Upstream Adapter
- Unit 1D: Routing & Circuit Breaker (minimal - Plan only)

---

## Part 1: Planning Questions

### Section A: Domain Entities

#### Question 1: User Status Transitions
What status transitions should be allowed for users?

A) Simple: active ↔ inactive (bidirectional)
B) One-way: active → inactive (no reactivation)
C) Extended: active → inactive → deleted (soft delete)
D) Other (please describe after [Answer]: tag below)

[Answer]: C

#### Question 2: Access Key Lifecycle
When an Access Key is rotated, what happens to the old key?

A) Immediately revoked (instant cutover)
B) Grace period (both keys valid for N minutes)
C) Manual revocation required after new key confirmed
D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

### Section B: Business Rules

#### Question 3: Access Key Validation Caching
When should the Access Key cache be invalidated?

A) Only on explicit revoke/rotate operations
B) On any status change (including user deactivation)
C) TTL-based only (60 seconds, no explicit invalidation)
D) Other (please describe after [Answer]: tag below)

[Answer]: B

#### Question 4: Circuit Breaker Scope
Should circuit breaker state be shared across multiple proxy instances?

A) Per-instance (in-memory, not shared)
B) Shared (Redis/database backed)
C) Hybrid (per-instance with periodic sync)
D) Other (please describe after [Answer]: tag below)

[Answer]: A

---

### Section C: Error Handling

#### Question 5: Anthropic API Passthrough
For non-rate-limit errors from Plan upstream, should the proxy:

A) Pass through the exact Anthropic error response
B) Normalize all errors to a standard proxy error format
C) Pass through with added proxy metadata (request_id)
D) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Part 2: Generation Checklist

### Shared Foundation
- [x] Generate domain-entities.md (User, AccessKey, BedrockKey, RequestLog, TokenUsage)
- [x] Generate business-rules.md (validation, key generation, hashing)
- [x] Generate business-logic-model.md (state machines, workflows)

### Unit 1A: Request Ingress & Auth
- [x] Generate business-logic-model.md (authentication flow) - included in shared
- [x] Generate business-rules.md (key validation rules) - included in shared

### Unit 1B: Plan Upstream Adapter
- [x] Generate business-logic-model.md (request transformation) - included in shared
- [x] Generate business-rules.md (error classification) - included in shared

### Unit 1D: Routing & Circuit Breaker
- [x] Generate business-logic-model.md (routing logic, circuit breaker) - included in shared
- [x] Generate business-rules.md (trigger conditions, reset policy) - included in shared

---

## Instructions

Please answer Questions 1-5 by filling in the letter choice (A, B, C, or D) after each [Answer]: tag.

Let me know when you've completed all answers.
