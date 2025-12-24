from aws_cdk import (
    Stack,
    CfnOutput,
    SecretValue,
    aws_amplify_alpha as amplify,
    aws_iam as iam,
    aws_codebuild as codebuild,
)
from constructs import Construct


class AmplifyStack(Stack):
    """Amplify Hosting stack for frontend deployment."""

    def __init__(
        self,
        scope: Construct,
        id: str,
        backend_url: str,
        repository_url: str,
        branch: str = "main",
        github_token_secret_name: str = "github-token",
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Create Amplify App
        self.amplify_app = amplify.App(
            self,
            "FrontendApp",
            app_name="claude-code-proxy-admin",
            source_code_provider=amplify.GitHubSourceCodeProvider(
                owner=self._extract_github_owner(repository_url),
                repository=self._extract_github_repo(repository_url),
                oauth_token=SecretValue.secrets_manager(github_token_secret_name),
            ),
            auto_branch_deletion=True,
            build_spec=codebuild.BuildSpec.from_object_to_yaml({
                "version": 1,
                "applications": [
                    {
                        "appRoot": "frontend",
                        "frontend": {
                            "phases": {
                                "preBuild": {
                                    "commands": [
                                        "npm ci",
                                    ]
                                },
                                "build": {
                                    "commands": [
                                        "npm run build",
                                    ]
                                },
                            },
                            "artifacts": {
                                "baseDirectory": ".next",
                                "files": ["**/*"],
                            },
                            "cache": {
                                "paths": ["node_modules/**/*"],
                            },
                        },
                    }
                ],
            }),
            environment_variables={
                "NEXT_PUBLIC_BACKEND_API_URL": backend_url,
                "AMPLIFY_MONOREPO_APP_ROOT": "frontend",
            },
            platform=amplify.Platform.WEB_COMPUTE,
        )

        # Add branch
        main_branch = self.amplify_app.add_branch(
            branch,
            auto_build=True,
            stage="PRODUCTION" if branch == "main" else "DEVELOPMENT",
        )

        # Outputs
        CfnOutput(
            self,
            "AmplifyAppId",
            value=self.amplify_app.app_id,
            description="Amplify App ID",
        )

        CfnOutput(
            self,
            "AmplifyAppUrl",
            value=f"https://{branch}.{self.amplify_app.default_domain}",
            description="Amplify App URL",
        )

        CfnOutput(
            self,
            "BackendApiUrl",
            value=backend_url,
            description="Backend API URL configured for frontend",
        )

    def _extract_github_owner(self, url: str) -> str:
        """Extract GitHub owner from repository URL."""
        # Handle both HTTPS and SSH URLs
        # https://github.com/owner/repo.git
        # git@github.com:owner/repo.git
        if "github.com" in url:
            if url.startswith("git@"):
                parts = url.split(":")[1].split("/")
            else:
                parts = url.replace("https://github.com/", "").split("/")
            return parts[0]
        raise ValueError(f"Invalid GitHub URL: {url}")

    def _extract_github_repo(self, url: str) -> str:
        """Extract GitHub repository name from URL."""
        if "github.com" in url:
            if url.startswith("git@"):
                parts = url.split(":")[1].split("/")
            else:
                parts = url.replace("https://github.com/", "").split("/")
            return parts[1].replace(".git", "")
        raise ValueError(f"Invalid GitHub URL: {url}")
