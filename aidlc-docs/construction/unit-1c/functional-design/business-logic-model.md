# Business Logic Model - Unit 1C: Bedrock Adapter

## Bedrock Adapter Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Bedrock Adapter Flow                          │
└─────────────────────────────────────────────────────────────────┘

    RequestContext + AnthropicRequest
                    │
                    ▼
           ┌────────────────┐
           │ Get Bedrock    │
           │ API Key        │
           └───────┬────────┘
                   │
                   ▼
           ┌────────────────┐
           │ Check Key      │
           │ Cache (TTL:5m) │
           └───────┬────────┘
                   │
      ┌────────────┴────────────┐
      │                         │
  cache hit                cache miss
      │                         │
      │                         ▼
      │                ┌────────────────┐
      │                │ Query DB for   │
      │                │ encrypted key  │
      │                └───────┬────────┘
      │                        │
      │                        ▼
      │                ┌────────────────┐
      │                │ KMS Decrypt    │
      │                └───────┬────────┘
      │                        │
      │                        ▼
      │                ┌────────────────┐
      │                │ Cache Result   │
      │                └───────┬────────┘
      │                        │
      └────────────┬───────────┘
                   │
                   ▼
           ┌────────────────┐
           │ Transform to   │
           │ Bedrock Format │
           └───────┬────────┘
                   │
                   ▼
           ┌────────────────┐
           │ Call Bedrock   │
           │ Converse API   │
           └───────┬────────┘
                   │
              ┌────┴────┐
              │         │
           success    error
              │         │
              ▼         ▼
    ┌─────────────┐  ┌─────────────────┐
    │ Transform   │  │ Classify Error  │
    │ Response to │  │ (auth, quota,   │
    │ Anthropic   │  │  unavailable)   │
    │ Format      │  └─────────────────┘
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │ Extract     │
    │ Token Usage │
    └─────────────┘
```

---

## Request Transformation: Anthropic → Bedrock

### Message Format Mapping

```
Anthropic Format:
{
  "model": "claude-3-5-sonnet-20241022",
  "max_tokens": 1024,
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "system": "You are helpful"
}

Bedrock Converse Format:
{
  "modelId": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "messages": [
    {"role": "user", "content": [{"text": "Hello"}]}
  ],
  "system": [{"text": "You are helpful"}],
  "inferenceConfig": {
    "maxTokens": 1024
  }
}
```

### Transformation Rules

| Anthropic Field | Bedrock Field | Transformation |
|-----------------|---------------|----------------|
| model | modelId | Map to Bedrock model ID |
| messages | messages | Wrap content in array |
| messages[].content (string) | messages[].content | `[{"text": content}]` |
| messages[].content (array) | messages[].content | Map content blocks |
| system (string) | system | `[{"text": system}]` |
| system (array) | system | Map system blocks |
| max_tokens | inferenceConfig.maxTokens | Direct map |
| temperature | inferenceConfig.temperature | Direct map |
| top_p | inferenceConfig.topP | Direct map |
| stop_sequences | inferenceConfig.stopSequences | Direct map |

### Content Block Mapping

```
Anthropic ContentBlock:
  {"type": "text", "text": "..."}
  {"type": "image", "source": {...}}
  {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
  {"type": "tool_result", "tool_use_id": "...", "content": "..."}

Bedrock ContentBlock:
  {"text": "..."}
  {"image": {"format": "...", "source": {...}}}
  {"toolUse": {"toolUseId": "...", "name": "...", "input": {...}}}
  {"toolResult": {"toolUseId": "...", "content": [...]}}
```

---

## Response Transformation: Bedrock → Anthropic

### Response Format Mapping

```
Bedrock Response:
{
  "output": {
    "message": {
      "role": "assistant",
      "content": [{"text": "Hello!"}]
    }
  },
  "stopReason": "end_turn",
  "usage": {
    "inputTokens": 10,
    "outputTokens": 5
  }
}

Anthropic Response:
{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "content": [{"type": "text", "text": "Hello!"}],
  "model": "claude-3-5-sonnet-20241022",
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 5
  }
}
```

### Transformation Rules

| Bedrock Field | Anthropic Field | Transformation |
|---------------|-----------------|----------------|
| output.message.content | content | Unwrap and add type |
| stopReason | stop_reason | snake_case |
| usage.inputTokens | usage.input_tokens | snake_case |
| usage.outputTokens | usage.output_tokens | snake_case |
| - | id | Generate `msg_{uuid}` |
| - | type | Always "message" |
| - | model | From request context |

---

## Token Usage Extraction

```python
def extract_usage(bedrock_response: dict) -> TokenUsage:
    usage = bedrock_response.get("usage", {})
    return TokenUsage(
        input_tokens=usage.get("inputTokens", 0),
        output_tokens=usage.get("outputTokens", 0),
        cache_read_input_tokens=usage.get("cacheReadInputTokens"),
        cache_creation_input_tokens=usage.get("cacheCreationInputTokens")
    )
```

---

## Error Classification

```python
def classify_bedrock_error(error: Exception) -> BedrockErrorType:
    error_str = str(error)
    error_code = getattr(error, 'response', {}).get('Error', {}).get('Code', '')
    
    if 'AccessDeniedException' in error_str or error_code == 'AccessDeniedException':
        return BedrockErrorType.AUTH_ERROR
    
    if 'ThrottlingException' in error_str or error_code == 'ThrottlingException':
        return BedrockErrorType.QUOTA_EXCEEDED
    
    if 'ValidationException' in error_str or error_code == 'ValidationException':
        return BedrockErrorType.VALIDATION_ERROR
    
    if 'ModelError' in error_str or error_code == 'ModelError':
        return BedrockErrorType.MODEL_ERROR
    
    return BedrockErrorType.UNAVAILABLE
```

---

## Bedrock API Call

### HTTP Request

```
POST https://bedrock-runtime.{region}.amazonaws.com/model/{modelId}/converse
Authorization: Bearer {bedrock_api_key}
Content-Type: application/json

{
  "messages": [...],
  "system": [...],
  "inferenceConfig": {...}
}
```

### Timeout Configuration

```
connect_timeout: 5 seconds
read_timeout: 300 seconds (5 minutes for long responses)
```
