#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.network_stack import NetworkStack
from stacks.secrets_stack import SecretsStack
from stacks.database_stack import DatabaseStack
from stacks.compute_stack import ComputeStack
from stacks.monitoring_stack import MonitoringStack
from stacks.amplify_stack import AmplifyStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "ap-northeast-2",
)

network = NetworkStack(app, "NetworkStack", env=env)
secrets = SecretsStack(app, "SecretsStack", env=env)
database = DatabaseStack(app, "DatabaseStack", vpc=network.vpc, db_sg=network.db_sg, env=env)
compute = ComputeStack(
    app,
    "ComputeStack",
    vpc=network.vpc,
    ecs_sg=network.ecs_sg,
    db_secret=database.db_secret,
    kms_key=secrets.kms_key,
    secrets=secrets,
    env=env,
)
MonitoringStack(
    app,
    "MonitoringStack",
    service_name=compute.service_name,
    service_arn=compute.service_arn,
    env=env,
)

# Amplify Stack for frontend deployment
# Configure these values via CDK context or environment variables
repository_url = app.node.try_get_context("repository_url") or "https://github.com/your-org/your-repo"
branch = app.node.try_get_context("branch") or "main"
github_token_secret = app.node.try_get_context("github_token_secret") or "github-token"

AmplifyStack(
    app,
    "AmplifyStack",
    backend_url=compute.backend_url,
    repository_url=repository_url,
    branch=branch,
    github_token_secret_name=github_token_secret,
    env=env,
)

app.synth()
