from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Environment
    environment: str = "dev"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/proxy"

    # Secrets (loaded from env or Secrets Manager)
    plan_api_key: str = ""
    key_hasher_secret: str = ""
    jwt_secret: str = ""
    admin_username: str = "admin"
    admin_password_hash: str = ""

    # KMS
    kms_key_id: str = ""
    local_encryption_key: str = ""

    # Cache TTLs
    access_key_cache_ttl: int = 60
    bedrock_key_cache_ttl: int = 300

    # Circuit Breaker
    circuit_failure_threshold: int = 3
    circuit_failure_window: int = 60
    circuit_reset_timeout: int = 1800

    # Timeouts
    http_connect_timeout: float = 5.0
    http_read_timeout: float = 300.0

    # URLs
    plan_api_url: str = "https://api.anthropic.com"
    bedrock_region: str = "ap-northeast-2"
    bedrock_default_model: str = "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
    plan_verify_ssl: bool = True
    plan_ca_bundle: str = ""
    plan_force_rate_limit: bool = False

    model_config = {"env_prefix": "PROXY_", "env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
