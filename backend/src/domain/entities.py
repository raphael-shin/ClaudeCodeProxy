from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .enums import UserStatus, KeyStatus


@dataclass
class User:
    id: UUID
    name: str
    description: str | None
    status: UserStatus
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


@dataclass
class AccessKey:
    id: UUID
    user_id: UUID
    key_hash: str
    key_prefix: str
    status: KeyStatus
    bedrock_region: str
    bedrock_model: str
    created_at: datetime
    revoked_at: datetime | None = None
    rotation_expires_at: datetime | None = None


@dataclass
class BedrockKey:
    access_key_id: UUID
    encrypted_key: bytes
    key_hash: str
    created_at: datetime
    rotated_at: datetime | None = None


@dataclass
class TokenUsage:
    id: UUID
    request_id: str
    timestamp: datetime
    user_id: UUID
    access_key_id: UUID
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int | None
    cache_creation_input_tokens: int | None
    total_tokens: int
    provider: str
    is_fallback: bool
    latency_ms: int


@dataclass
class UsageAggregate:
    id: UUID
    bucket_type: str
    bucket_start: datetime
    user_id: UUID
    access_key_id: UUID | None
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
