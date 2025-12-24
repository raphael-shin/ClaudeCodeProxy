from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
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
        ecs_sg: ec2.SecurityGroup,
        db_secret: secretsmanager.ISecret,
        kms_key: kms.Key,
        secrets,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Build container image from backend directory
        image_asset = ecr_assets.DockerImageAsset(
            self, "BackendImage", directory="../backend"
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

        # Create infrastructure role for Express Mode
        infrastructure_role = iam.Role(
            self,
            "InfrastructureRole",
            assumed_by=iam.ServicePrincipal("ecs.amazonaws.com"),
        )

        # Add required permissions for Express Gateway infrastructure role
        # Using broad permissions as the managed policy is not yet available
        infra_policy = iam.Policy(
            self,
            "InfrastructurePolicy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "ec2:*",
                        "elasticloadbalancing:*",
                        "logs:*",
                        "ecs:*",
                        "ecr:*",
                        "servicediscovery:*",
                        "cloudwatch:*",
                        "autoscaling:*",
                        "application-autoscaling:*",
                        "iam:PassRole",
                        "iam:CreateServiceLinkedRole",
                    ],
                    resources=["*"],
                )
            ],
        )
        infrastructure_role.attach_inline_policy(infra_policy)

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

        # Get private subnets for network configuration
        private_subnets = vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        )

        # Create ECS Express Gateway Service - minimal config
        self.express_service = ecs.CfnExpressGatewayService(
            self,
            "ProxyExpressService",
            service_name="claude-code-proxy",
            execution_role_arn=execution_role.role_arn,
            infrastructure_role_arn=infrastructure_role.role_arn,
            task_role_arn=task_role.role_arn,
            primary_container=ecs.CfnExpressGatewayService.ExpressGatewayContainerProperty(
                image=image_asset.image_uri,
                container_port=8000,
                environment=[
                    ecs.CfnExpressGatewayService.KeyValuePairProperty(
                        name="ENVIRONMENT", value="dev"
                    ),
                    ecs.CfnExpressGatewayService.KeyValuePairProperty(
                        name="LOG_LEVEL", value="INFO"
                    ),
                    ecs.CfnExpressGatewayService.KeyValuePairProperty(
                        name="PROXY_KMS_KEY_ID", value=kms_key.key_id
                    ),
                    ecs.CfnExpressGatewayService.KeyValuePairProperty(
                        name="PROXY_DATABASE_URL_ARN", value=db_secret.secret_arn
                    ),
                    ecs.CfnExpressGatewayService.KeyValuePairProperty(
                        name="PROXY_KEY_HASHER_SECRET_ARN", value=secrets.key_hasher_secret.secret_arn
                    ),
                    ecs.CfnExpressGatewayService.KeyValuePairProperty(
                        name="PROXY_JWT_SECRET_ARN", value=secrets.jwt_secret.secret_arn
                    ),
                    ecs.CfnExpressGatewayService.KeyValuePairProperty(
                        name="PROXY_ADMIN_CREDENTIALS_ARN", value=secrets.admin_credentials.secret_arn
                    ),
                ],
            ),
            network_configuration=ecs.CfnExpressGatewayService.ExpressGatewayServiceNetworkConfigurationProperty(
                subnets=private_subnets.subnet_ids,
            ),
        )

        # Ensure policy is created before the service
        self.express_service.node.add_dependency(infra_policy)

        # Store service ARN for monitoring
        self.service_name = "ProxyExpressService"
        self.service_arn = self.express_service.attr_service_arn

        # Export backend URL for frontend integration
        self.backend_url = f"https://{self.express_service.attr_endpoint}"
