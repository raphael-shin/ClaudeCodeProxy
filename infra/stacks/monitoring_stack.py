from aws_cdk import (
    Stack,
    Duration,
    Fn,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
)
from constructs import Construct


class MonitoringStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        service_name: str,
        service_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Parse cluster name from ECS service ARN (arn:...:service/cluster-name/service-name).
        cluster_name = Fn.select(0, Fn.split("/", Fn.select(5, Fn.split(":", service_arn))))

        namespace = "ClaudeCodeProxy"

        dashboard = cloudwatch.Dashboard(self, "ProxyDashboard", dashboard_name="ClaudeCodeProxy")

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Request Count",
                left=[
                    cloudwatch.Metric(
                        namespace=namespace,
                        metric_name="RequestCount",
                        dimensions_map={"Provider": "plan"},
                        statistic="Sum",
                        period=Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace=namespace,
                        metric_name="RequestCount",
                        dimensions_map={"Provider": "bedrock"},
                        statistic="Sum",
                        period=Duration.minutes(5),
                    ),
                ],
            ),
            cloudwatch.GraphWidget(
                title="Latency (p95)",
                left=[
                    cloudwatch.Metric(
                        namespace=namespace,
                        metric_name="RequestLatency",
                        dimensions_map={"Provider": "plan"},
                        statistic="p95",
                        period=Duration.minutes(5),
                    ),
                    cloudwatch.Metric(
                        namespace=namespace,
                        metric_name="RequestLatency",
                        dimensions_map={"Provider": "bedrock"},
                        statistic="p95",
                        period=Duration.minutes(5),
                    ),
                ],
            ),
        )

        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="ECS CPU Utilization",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/ECS",
                        metric_name="CPUUtilization",
                        dimensions_map={
                            "ClusterName": cluster_name,
                            "ServiceName": service_name,
                        },
                        statistic="Average",
                        period=Duration.minutes(5),
                    ),
                ],
            ),
            cloudwatch.GraphWidget(
                title="ECS Memory Utilization",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/ECS",
                        metric_name="MemoryUtilization",
                        dimensions_map={
                            "ClusterName": cluster_name,
                            "ServiceName": service_name,
                        },
                        statistic="Average",
                        period=Duration.minutes(5),
                    ),
                ],
            ),
        )

        alert_topic = sns.Topic(self, "AlertTopic")

        cloudwatch.Alarm(
            self,
            "HighErrorRate",
            metric=cloudwatch.Metric(
                namespace=namespace,
                metric_name="ErrorCount",
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=10,
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        ).add_alarm_action(cw_actions.SnsAction(alert_topic))

        cloudwatch.Alarm(
            self,
            "HighCpuUtilization",
            metric=cloudwatch.Metric(
                namespace="AWS/ECS",
                metric_name="CPUUtilization",
                dimensions_map={
                    "ClusterName": cluster_name,
                    "ServiceName": service_name,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=90,
            evaluation_periods=3,
        ).add_alarm_action(cw_actions.SnsAction(alert_topic))
