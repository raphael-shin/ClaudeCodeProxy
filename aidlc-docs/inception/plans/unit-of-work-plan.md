# Unit of Work Plan - ClaudeCodeProxy

## Overview
This plan finalizes the decomposition of ClaudeCodeProxy into 8 units of work, as defined in the execution plan.

## Pre-Defined Units (from Execution Plan)

| Unit | Name | Type |
|------|------|------|
| 1A | Request Ingress & Auth | Module (Proxy) |
| 1B | Plan Upstream Adapter | Module (Proxy) |
| 1C | Bedrock Adapter | Module (Proxy) |
| 1D | Routing & Circuit Breaker | Module (Proxy) |
| 1E | Usage Metering & Observability | Module (Proxy) |
| 2 | Admin Backend | Service |
| 3 | Admin Frontend | Service |
| 4 | Infrastructure | CDK Stack |

---

## Part 1: Planning Questions

### Section A: Development Sequence

#### Question 1: Unit Development Order
In what order should units be developed? (Consider dependencies)

A) Infrastructure first, then parallel development of all other units
B) Sequential: 4 → 1A → 1B → 1C → 1D → 1E → 2 → 3
C) Parallel tracks: (4 + 1A-1E) in parallel with (2 + 3)
D) Other (please describe after [Answer]: tag below)

[Answer]: D) - Recommended order (hybrid, risk-first):
	1.	Shared foundation (minimal) + Infra-A (foundation) in parallel
	•	Shared: core types, config, logging, DB session factory, repo interfaces (stubs)
	•	Infra-A: VPC/ALB/ECS base, Aurora, KMS, Secrets (no app wiring yet)
	2.	Proxy core path first (vertical slice)
	•	1A (Ingress/Auth) → 1B (Plan Adapter) → 1D (Router minimal)
	•	Goal: “Plan-only success path” end-to-end as soon as possible.
	3.	Bedrock fallback path
	•	1C (Bedrock Adapter) (incl. BedrockKey decrypt + TTL cache)
	•	Extend 1D to support fallback + circuit breaker criteria.
	4.	Metering/observability
	•	1E (Usage + metrics) with “request log always, tokens for bedrock only”.
	5.	Admin backend then frontend
	•	2 (Admin Backend) (users, AK, bedrock key, usage query)
	•	3 (Admin Frontend)
	6.	Infra-B (service binding)
	•	ECS service wiring, autoscaling, log groups, alarms, rollout config

#### Question 2: Shared Module Priority
The `shared/` module contains models, repositories, and utilities used by both Proxy and Admin. When should it be developed?

A) First, before any other unit (foundation)
B) Incrementally, as each unit needs it
C) Split: Core models first, then extend per-unit
D) Other (please describe after [Answer]: tag below)

[Answer]: C

---

### Section B: Integration Strategy

#### Question 3: Database Schema Ownership
Which unit should own the database schema migrations?

A) Unit 4 (Infrastructure) - schema as part of CDK deployment
B) Shared module - separate migration scripts
C) Unit 2 (Admin Backend) - since it manages all entities
D) Other (please describe after [Answer]: tag below)

[Answer]: B

#### Question 4: Testing Strategy per Unit
How should each unit be tested before integration?

A) Unit tests only - integration tests at the end
B) Unit tests + contract tests between units
C) Unit tests + mock integration tests per unit
D) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## Part 2: Generation Checklist

After questions are answered, the following artifacts will be generated:

### Unit Definitions
- [x] Generate unit-of-work.md with detailed unit specifications
- [x] Define responsibilities, inputs, outputs for each unit
- [x] Specify technology stack per unit

### Unit Dependencies
- [x] Generate unit-of-work-dependency.md with dependency matrix
- [x] Define build-time vs runtime dependencies
- [x] Specify integration points between units

### Story Mapping
- [x] Generate unit-of-work-story-map.md mapping stories to units
- [x] Ensure all 20 user stories are assigned
- [x] Validate coverage completeness

### Development Sequence
- [x] Define recommended development order
- [x] Identify parallelization opportunities
- [x] Document critical path

---

## Instructions

Please answer Questions 1-4 by filling in the letter choice (A, B, C, or D) after each [Answer]: tag.

If you choose "Other" (D), please provide a brief description of your preference.

Let me know when you've completed all answers so I can proceed with unit generation.
