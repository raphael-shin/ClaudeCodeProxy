from aws_cdk import Stack, aws_ec2 as ec2
from constructs import Construct


class NetworkStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.vpc = ec2.Vpc(
            self,
            "ProxyVpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # ALB Security Group - Restricted to CloudFront only
        self.alb_sg = ec2.SecurityGroup(
            self,
            "AlbSg",
            vpc=self.vpc,
            description="ALB Security Group - CloudFront Prefix List only",
        )

        # Use AWS-managed CloudFront prefix list for origin-facing traffic
        # This restricts ALB access to only CloudFront IP ranges
        cloudfront_prefix_list_id = ec2.Peer.prefix_list("pl-22a6434b")  # ap-northeast-2

        self.alb_sg.add_ingress_rule(
            cloudfront_prefix_list_id,
            ec2.Port.tcp(443),
            "HTTPS from CloudFront only",
        )
        self.alb_sg.add_ingress_rule(
            cloudfront_prefix_list_id,
            ec2.Port.tcp(80),
            "HTTP from CloudFront only",
        )

        self.ecs_sg = ec2.SecurityGroup(self, "EcsSg", vpc=self.vpc)
        self.ecs_sg.add_ingress_rule(self.alb_sg, ec2.Port.tcp(8000))

        self.db_sg = ec2.SecurityGroup(self, "DbSg", vpc=self.vpc)
        self.db_sg.add_ingress_rule(self.ecs_sg, ec2.Port.tcp(5432))
