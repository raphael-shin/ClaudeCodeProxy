# Infrastructure Design - ClaudeCodeProxy

## Deployment Decisions

| Decision | Choice | Description |
|----------|--------|-------------|
| Environment | Single (dev) | 개발/테스트용 단일 환경 |
| Domain | Custom + ACM | Route 53 + ACM 인증서 |
| CI/CD | Manual CDK | CDK CLI로 수동 배포 |
| Backup | 7 days | 기본 백업 정책 |
| Cost | Balanced | 비용과 성능 균형 |

---

## CDK Project Structure

```
infra/
├── app.py                    # CDK app entry point
├── cdk.json                  # CDK configuration
├── requirements.txt          # Python dependencies
└── stacks/
    ├── __init__.py
    ├── network_stack.py      # VPC, subnets, security groups
    ├── database_stack.py     # Aurora PostgreSQL
    ├── secrets_stack.py      # Secrets Manager, KMS
    ├── compute_stack.py      # ECS Fargate, ALB
    └── monitoring_stack.py   # CloudWatch dashboards, alarms
```

---

## Stack Dependencies

```
┌─────────────────┐
│  NetworkStack   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌─────────┐
│Secrets │ │Database │
│ Stack  │ │ Stack   │
└───┬────┘ └────┬────┘
    │           │
    └─────┬─────┘
          │
          ▼
   ┌──────────────┐
   │ ComputeStack │
   └──────┬───────┘
          │
          ▼
   ┌──────────────┐
   │MonitoringStack│
   └──────────────┘
```

---

## Network Stack

```python
# VPC Configuration
vpc = ec2.Vpc(
    self, "ProxyVpc",
    max_azs=2,
    nat_gateways=1,
    subnet_configuration=[
        ec2.SubnetConfiguration(
            name="Public",
            subnet_type=ec2.SubnetType.PUBLIC,
            cidr_mask=24
        ),
        ec2.SubnetConfiguration(
            name="Private",
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            cidr_mask=24
        )
    ]
)

# Security Groups
alb_sg = ec2.SecurityGroup(self, "AlbSg", vpc=vpc)
alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443))
alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80))

ecs_sg = ec2.SecurityGroup(self, "EcsSg", vpc=vpc)
ecs_sg.add_ingress_rule(alb_sg, ec2.Port.tcp(8000))

db_sg = ec2.SecurityGroup(self, "DbSg", vpc=vpc)
db_sg.add_ingress_rule(ecs_sg, ec2.Port.tcp(5432))
```

---

## Database Stack

```python
# Aurora PostgreSQL Serverless v2
cluster = rds.DatabaseCluster(
    self, "ProxyDb",
    engine=rds.DatabaseClusterEngine.aurora_postgres(
        version=rds.AuroraPostgresEngineVersion.VER_15_4
    ),
    serverless_v2_min_capacity=0.5,
    serverless_v2_max_capacity=4,
    writer=rds.ClusterInstance.serverless_v2("writer"),
    vpc=vpc,
    vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
    security_groups=[db_sg],
    storage_encrypted=True,
    backup=rds.BackupProps(retention=Duration.days(7)),
    credentials=rds.Credentials.from_generated_secret("postgres")
)
```

---

## Secrets Stack

```python
# KMS Key for Bedrock API key encryption
kms_key = kms.Key(
    self, "ProxyKmsKey",
    alias="alias/claude-code-proxy",
    enable_key_rotation=True
)

# Secrets
# The proxy forwards client Authorization/x-api-key by default.
# If you want a default Plan key, create the secret manually and wire it in.
admin_credentials = secretsmanager.Secret(
    self, "AdminCredentials",
    secret_name="claude-code-proxy/admin-credentials",
    generate_secret_string=secretsmanager.SecretStringGenerator(
        secret_string_template='{"username": "admin"}',
        generate_string_key="password"
    )
)

key_hasher_secret = secretsmanager.Secret(
    self, "KeyHasherSecret",
    secret_name="claude-code-proxy/key-hasher-secret",
    generate_secret_string=secretsmanager.SecretStringGenerator(
        password_length=64,
        exclude_punctuation=True
    )
)
```

---

## Compute Stack

```python
# ECS Cluster
cluster = ecs.Cluster(self, "ProxyCluster", vpc=vpc)

# Task Definition
task_def = ecs.FargateTaskDefinition(
    self, "ProxyTask",
    cpu=512,
    memory_limit_mib=1024
)

container = task_def.add_container(
    "proxy",
    image=ecs.ContainerImage.from_asset("../backend"),
    port_mappings=[ecs.PortMapping(container_port=8000)],
    logging=ecs.LogDrivers.aws_logs(stream_prefix="proxy"),
    environment={
        "ENVIRONMENT": "dev",
        "LOG_LEVEL": "INFO"
    },
    secrets={
        "DATABASE_URL": ecs.Secret.from_secrets_manager(db_secret),
        "KEY_HASHER_SECRET": ecs.Secret.from_secrets_manager(key_hasher_secret)
    }
)

# ALB
alb = elbv2.ApplicationLoadBalancer(
    self, "ProxyAlb",
    vpc=vpc,
    internet_facing=True,
    security_group=alb_sg
)

# HTTPS Listener (requires certificate)
certificate = acm.Certificate(
    self, "ProxyCert",
    domain_name="proxy.example.com",  # Replace with actual domain
    validation=acm.CertificateValidation.from_dns()
)

https_listener = alb.add_listener(
    "HttpsListener",
    port=443,
    certificates=[certificate]
)

# HTTP redirect
alb.add_listener(
    "HttpListener",
    port=80,
    default_action=elbv2.ListenerAction.redirect(
        port="443",
        protocol="HTTPS",
        permanent=True
    )
)

# ECS Service
service = ecs.FargateService(
    self, "ProxyService",
    cluster=cluster,
    task_definition=task_def,
    desired_count=2,
    security_groups=[ecs_sg],
    vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
)

# Auto-scaling
scaling = service.auto_scale_task_count(min_capacity=2, max_capacity=10)
scaling.scale_on_cpu_utilization("CpuScaling", target_utilization_percent=70)
scaling.scale_on_memory_utilization("MemoryScaling", target_utilization_percent=80)

# Target Group
https_listener.add_targets(
    "ProxyTarget",
    port=8000,
    targets=[service],
    health_check=elbv2.HealthCheck(path="/health", interval=Duration.seconds(30))
)
```

---

## Monitoring Stack

```python
# Dashboard
dashboard = cloudwatch.Dashboard(self, "ProxyDashboard", dashboard_name="ClaudeCodeProxy")

# Alarms
error_alarm = cloudwatch.Alarm(
    self, "HighErrorRate",
    metric=cloudwatch.Metric(
        namespace="ClaudeCodeProxy",
        metric_name="ErrorCount",
        statistic="Sum",
        period=Duration.minutes(5)
    ),
    threshold=10,
    evaluation_periods=3,
    comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
)

# SNS Topic for alerts
alert_topic = sns.Topic(self, "AlertTopic")
error_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alert_topic))
```

---

## IAM Permissions

```python
# ECS Task Role permissions
task_def.task_role.add_to_policy(iam.PolicyStatement(
    actions=["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"],
    resources=[kms_key.key_arn]
))

task_def.task_role.add_to_policy(iam.PolicyStatement(
    actions=["secretsmanager:GetSecretValue"],
    resources=[
        admin_credentials.secret_arn,
        key_hasher_secret.secret_arn,
        db_secret.secret_arn
    ]
))

task_def.task_role.add_to_policy(iam.PolicyStatement(
    actions=["cloudwatch:PutMetricData"],
    resources=["*"],
    conditions={"StringEquals": {"cloudwatch:namespace": "ClaudeCodeProxy"}}
))

# NOTE: This proxy uses Bedrock Converse with Bearer tokens by default, so
# InvokeModel permissions are not required. Keep only if you plan to use SigV4.
task_def.task_role.add_to_policy(iam.PolicyStatement(
    actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
    resources=["*"]
))
```

---

## Deployment Commands

```bash
# Install dependencies
cd infra
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy all stacks
cdk deploy --all

# Deploy specific stack
cdk deploy ComputeStack

# Destroy all stacks
cdk destroy --all
```
