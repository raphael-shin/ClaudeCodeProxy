from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_kms as kms,
    aws_secretsmanager as secretsmanager,
    aws_ecr_assets as ecr_assets,
)
from constructs import Construct


class ComputeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        alb_sg: ec2.SecurityGroup,
        ecs_sg: ec2.SecurityGroup,
        db_secret: secretsmanager.ISecret,
        kms_key: kms.Key,
        secrets,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Build container image from backend directory
        image_asset = ecr_assets.DockerImageAsset(
            self,
            "BackendImage",
            directory="../backend",
            platform=ecr_assets.Platform.LINUX_ARM64,
        )

        # Create execution role for ECS tasks
        execution_role = iam.Role(
            self,
            "ExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )

        # Create task role with required permissions
        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"],
                resources=[kms_key.key_arn],
            )
        )
        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": "ClaudeCodeProxy"}},
            )
        )
        task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=["*"],
            )
        )
        # Grant secrets access to task role
        db_secret.grant_read(task_role)
        secrets.key_hasher_secret.grant_read(task_role)
        secrets.jwt_secret.grant_read(task_role)
        secrets.admin_credentials.grant_read(task_role)

        private_subnets = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        )

        cluster = ecs.Cluster(self, "ProxyCluster", vpc=vpc)

        load_balancer = elbv2.ApplicationLoadBalancer(
            self,
            "ProxyAlb",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_sg,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "ProxyService",
            cluster=cluster,
            service_name="claude-code-proxy",
            load_balancer=load_balancer,
            public_load_balancer=True,
            open_listener=False,
            desired_count=1,
            assign_public_ip=False,
            task_subnets=private_subnets,
            security_groups=[ecs_sg],
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_docker_image_asset(image_asset),
                container_port=8000,
                environment={
                    "ENVIRONMENT": "dev",
                    "LOG_LEVEL": "INFO",
                    "PROXY_KMS_KEY_ID": kms_key.key_id,
                    "PROXY_DATABASE_URL_ARN": db_secret.secret_arn,
                    "PROXY_KEY_HASHER_SECRET_ARN": secrets.key_hasher_secret.secret_arn,
                    "PROXY_JWT_SECRET_ARN": secrets.jwt_secret.secret_arn,
                    "PROXY_ADMIN_CREDENTIALS_ARN": secrets.admin_credentials.secret_arn,
                },
                execution_role=execution_role,
                task_role=task_role,
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="claude-code-proxy"
                ),
            ),
        )

        fargate_service.target_group.configure_health_check(path="/health")

        # Store service ARN for monitoring
        self.service_name = fargate_service.service.service_name
        self.service_arn = fargate_service.service.service_arn

        # Export backend URL for frontend integration
        self.backend_url = f"http://{fargate_service.load_balancer.load_balancer_dns_name}"
