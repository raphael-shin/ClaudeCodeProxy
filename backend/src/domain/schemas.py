from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime
from uuid import UUID


# Anthropic API compatible schemas
class AnthropicMessage(BaseModel):
    role: str
    content: str | list | dict


class AnthropicRequest(BaseModel):
    model: str
    messages: list[AnthropicMessage]
    max_tokens: int | None = 4096
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    stop_sequences: list[str] | None = None
    stream: bool = False
    system: str | list | None = None
    metadata: dict[str, Any] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: dict[str, Any] | None = None
    thinking: dict[str, Any] | None = None
    original_model: str | None = None


class AnthropicUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None


class AnthropicResponse(BaseModel):
    id: str
    type: str = "message"
    role: str = "assistant"
    content: list[dict]
    model: str
    stop_reason: str | None = None
    stop_sequence: str | None = None
    usage: AnthropicUsage


class AnthropicError(BaseModel):
    type: str = "error"
    error: dict
    request_id: str | None = None


class AnthropicCountTokensResponse(BaseModel):
    input_tokens: int


# Admin API schemas
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class UserResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class AccessKeyCreate(BaseModel):
    bedrock_region: str = "ap-northeast-2"
    bedrock_model: str | None = None


class AccessKeyResponse(BaseModel):
    id: UUID
    key_prefix: str
    status: str
    bedrock_region: str
    bedrock_model: str
    created_at: datetime
    raw_key: str | None = None  # Only on creation


class BedrockKeyRegister(BaseModel):
    bedrock_api_key: str = Field(min_length=1)


class UsageQueryParams(BaseModel):
    user_id: UUID | None = None
    access_key_id: UUID | None = None
    bucket_type: str = "hour"
    start_time: datetime | None = None
    end_time: datetime | None = None


class UsageBucket(BaseModel):
    bucket_start: datetime
    requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int


class UsageResponse(BaseModel):
    buckets: list[UsageBucket]
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int


class UsageTopUser(BaseModel):
    user_id: UUID
    name: str
    total_tokens: int
    total_requests: int
