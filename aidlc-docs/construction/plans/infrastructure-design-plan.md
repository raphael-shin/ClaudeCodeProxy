# Infrastructure Design Plan - ClaudeCodeProxy

## Overview
NFR Design에서 논리적 컴포넌트가 이미 상세히 정의되어 있습니다. 이 단계에서는 실제 배포를 위한 추가 결정사항을 확정합니다.

## Pre-defined Infrastructure (from NFR Design)
- Compute: ECS Fargate (0.5 vCPU, 1GB)
- Database: Aurora PostgreSQL Serverless v2 (0.5-4 ACU)
- Load Balancer: ALB with TLS termination
- Security: KMS, Secrets Manager
- Networking: VPC with public/private subnets
- Observability: CloudWatch Logs/Metrics/Alarms

---

## Questions

### 1. Environment Strategy
배포 환경 구성을 어떻게 할까요?

A) Single environment (dev only) - 개발/테스트용 단일 환경
B) Two environments (dev + prod) - 개발과 운영 분리
C) Three environments (dev + staging + prod) - 전체 파이프라인

[Answer]: A

### 2. Domain & Certificate
도메인 및 인증서 설정:

A) No custom domain - ALB 기본 DNS 사용
B) Custom domain with ACM - Route 53 + ACM 인증서
C) Bring your own certificate - 기존 인증서 사용

[Answer]: B

### 3. CI/CD Pipeline
배포 파이프라인 구성:

A) Manual deployment - CDK CLI로 수동 배포
B) GitHub Actions - GitHub 기반 CI/CD
C) AWS CodePipeline - AWS 네이티브 파이프라인
D) Other (specify)

[Answer]: A

### 4. Database Backup Strategy
데이터베이스 백업 전략:

A) Default (7 days retention, daily snapshots)
B) Extended (30 days retention, point-in-time recovery)
C) Custom (specify retention period)

[Answer]: A

### 5. Cost Optimization
비용 최적화 우선순위:

A) Cost-first - 최소 비용 (dev 환경에 적합)
B) Balanced - 비용과 성능 균형
C) Performance-first - 성능 우선 (prod 환경에 적합)

[Answer]: B

---

## Generation Steps

- [ ] Analyze answers and resolve ambiguities
- [ ] Generate infrastructure-design.md (AWS CDK 구조)
- [ ] Generate deployment-architecture.md (환경별 배포 구성)
- [ ] Update aidlc-state.md
