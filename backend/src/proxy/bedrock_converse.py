import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

from botocore.eventstream import EventStreamBuffer
from botocore.loaders import Loader
from botocore.model import ServiceModel
from botocore.parsers import EventStreamJSONParser

try:
    from ..domain import AnthropicRequest, AnthropicResponse, AnthropicUsage
except ImportError:  # pragma: no cover - fallback for tests without package context
    from domain import AnthropicRequest, AnthropicResponse, AnthropicUsage


_response_stream_shape_cache = None


def _get_response_stream_shape():
    global _response_stream_shape_cache
    if _response_stream_shape_cache is None:
        loader = Loader()
        service_dict = loader.load_service_model("bedrock-runtime", "service-2")
        service_model = ServiceModel(service_dict)
        _response_stream_shape_cache = service_model.shape_for("ResponseStream")
    return _response_stream_shape_cache


def build_converse_request(request: AnthropicRequest) -> dict[str, Any]:
    messages = [_normalize_message(msg) for msg in request.messages]
    payload: dict[str, Any] = {"messages": messages}

    system_blocks = _normalize_system(request.system)
    if system_blocks:
        payload["system"] = system_blocks

    inference_config = _build_inference_config(request)
    if inference_config:
        payload["inferenceConfig"] = inference_config

    tool_config = _build_tool_config(request.tools, request.tool_choice)
    if tool_config:
        payload["toolConfig"] = tool_config

    request_metadata = _normalize_request_metadata(request.metadata)
    if request_metadata:
        payload["requestMetadata"] = request_metadata

    return payload


def parse_converse_response(
    data: dict[str, Any],
    model: str,
) -> tuple[AnthropicResponse, AnthropicUsage]:
    message = data.get("output", {}).get("message", {}) or {}
    content_blocks = _normalize_output_content(message.get("content", []))

    usage_data = data.get("usage", {}) or {}
    usage = AnthropicUsage(
        input_tokens=usage_data.get("inputTokens", 0),
        output_tokens=usage_data.get("outputTokens", 0),
        cache_read_input_tokens=usage_data.get("cacheReadInputTokens"),
        cache_creation_input_tokens=usage_data.get("cacheCreationInputTokens"),
    )

    response = AnthropicResponse(
        id=data.get("id", f"msg_{hash(json.dumps(data, sort_keys=True))}"),
        content=content_blocks,
        model=model,
        stop_reason=_normalize_stop_reason(data.get("stopReason")),
        stop_sequence=None,
        usage=usage,
    )
    return response, usage


@dataclass
class StreamState:
    message_id: str
    stop_reason: str | None = None
    usage: dict[str, Any] | None = None
    message_started: bool = False
    message_stopped: bool = False


class ConverseStreamDecoder:
    def __init__(self) -> None:
        self._parser = EventStreamJSONParser()
        self._buffer = EventStreamBuffer()

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        self._buffer.add_data(chunk)
        for event in self._buffer:
            response_dict = event.to_response_dict()
            parsed = self._parser.parse(response_dict, _get_response_stream_shape())
            if response_dict["status_code"] != 200:
                raise ValueError(response_dict.get("body", b"").decode(errors="ignore"))
            payload = None
            if "chunk" in parsed and parsed["chunk"]:
                payload = parsed["chunk"].get("bytes")
            elif response_dict.get("body"):
                payload = response_dict["body"]
            if not payload:
                continue
            events.append(json.loads(payload.decode()))
        return events


async def iter_anthropic_sse(
    response_stream: AsyncIterator[bytes],
    model: str,
    message_id: str,
) -> AsyncIterator[bytes]:
    decoder = ConverseStreamDecoder()
    state = StreamState(message_id=message_id)

    async for chunk in response_stream:
        for event in decoder.feed(chunk):
            async for payload in _convert_converse_event(event, state, model):
                yield _to_sse(payload)

    async for payload in _flush_message_delta(state):
        yield _to_sse(payload)
    if state.message_started and not state.message_stopped:
        yield _to_sse({"type": "message_stop"})


def _normalize_message(message: Any) -> dict[str, Any]:
    content = _normalize_content(message.content)
    return {"role": message.role, "content": content}


def _normalize_content(content: Any) -> list[dict[str, Any]]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{"text": content}]
    if isinstance(content, dict):
        return [_normalize_content_block(content)]
    if isinstance(content, list):
        blocks = []
        for item in content:
            blocks.append(_normalize_content_block(item))
        return blocks
    return [{"text": json.dumps(content)}]


def _normalize_system(system: Any) -> list[dict[str, Any]]:
    if system is None:
        return []
    if isinstance(system, str):
        return [{"text": system}]
    if isinstance(system, dict):
        return [_normalize_system_block(system)]
    if isinstance(system, list):
        return [_normalize_system_block(item) for item in system]
    return [{"text": json.dumps(system)}]


def _normalize_system_block(block: Any) -> dict[str, Any]:
    if isinstance(block, str):
        return {"text": block}
    if isinstance(block, dict):
        if block.get("type") == "text" and "text" in block:
            return {"text": block["text"]}
        if "text" in block:
            return {"text": block["text"]}
    return {"text": json.dumps(block)}


def _normalize_content_block(block: Any) -> dict[str, Any]:
    if isinstance(block, str):
        return {"text": block}
    if not isinstance(block, dict):
        return {"text": json.dumps(block)}

    block_type = block.get("type")
    if block_type == "text":
        return {"text": block.get("text", "")}
    if block_type == "tool_use":
        return {
            "toolUse": {
                "toolUseId": block.get("id"),
                "name": block.get("name"),
                "input": block.get("input", {}),
            }
        }
    if block_type == "tool_result":
        tool_use_id = block.get("tool_use_id") or block.get("toolUseId")
        return {
            "toolResult": {
                "toolUseId": tool_use_id,
                "content": _normalize_tool_result_content(block.get("content")),
                "status": "error" if block.get("is_error") else "success",
            }
        }

    if "text" in block:
        return {"text": block["text"]}
    if "toolUse" in block or "toolResult" in block:
        return block

    return {"text": json.dumps(block)}


def _normalize_tool_result_content(content: Any) -> list[dict[str, Any]]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{"text": content}]
    if isinstance(content, dict):
        return [_normalize_content_block(content)]
    if isinstance(content, list):
        return [_normalize_content_block(item) for item in content]
    return [{"text": json.dumps(content)}]


def _normalize_tool_result_output_content(content: Any) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        return []
    output: list[dict[str, Any]] = []
    for block in content:
        if isinstance(block, dict) and "text" in block:
            output.append({"type": "text", "text": block["text"]})
    return output


def _build_inference_config(request: AnthropicRequest) -> dict[str, Any]:
    inference: dict[str, Any] = {}
    if request.max_tokens is not None:
        inference["maxTokens"] = request.max_tokens
    if request.temperature is not None:
        inference["temperature"] = request.temperature
    if request.top_p is not None:
        inference["topP"] = request.top_p
    if request.top_k is not None:
        inference["topK"] = request.top_k
    if request.stop_sequences:
        inference["stopSequences"] = request.stop_sequences
    return inference


def _build_tool_config(
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | str | None,
) -> dict[str, Any] | None:
    if not tools:
        return None
    tool_blocks = [_normalize_tool(tool) for tool in tools]
    tool_config: dict[str, Any] = {"tools": tool_blocks}
    choice_block = _normalize_tool_choice(tool_choice)
    if choice_block:
        tool_config["toolChoice"] = choice_block
    return tool_config


def _normalize_tool(tool: dict[str, Any]) -> dict[str, Any]:
    if "toolSpec" in tool:
        return {"toolSpec": tool["toolSpec"]}
    if tool.get("type") == "function" and "function" in tool:
        func = tool.get("function", {})
        return {
            "toolSpec": {
                "name": func.get("name") or tool.get("name"),
                "description": func.get("description"),
                "inputSchema": {"json": func.get("parameters", {})},
            }
        }
    return {
        "toolSpec": {
            "name": tool.get("name"),
            "description": tool.get("description"),
            "inputSchema": {"json": tool.get("input_schema", {})},
        }
    }


def _normalize_tool_choice(choice: dict[str, Any] | str | None) -> dict[str, Any] | None:
    if choice is None:
        return None
    if isinstance(choice, str):
        if choice == "auto":
            return {"auto": {}}
        if choice in ("any", "required"):
            return {"any": {}}
        return None
    choice_type = choice.get("type")
    if choice_type == "auto":
        return {"auto": {}}
    if choice_type in ("any", "required"):
        return {"any": {}}
    if choice_type == "tool":
        name = choice.get("name")
        if name:
            return {"tool": {"name": name}}
    tool_choice = choice.get("tool") or choice.get("function")
    if isinstance(tool_choice, dict) and tool_choice.get("name"):
        return {"tool": {"name": tool_choice["name"]}}
    return None


def _normalize_request_metadata(metadata: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(metadata, dict):
        return None
    cleaned: dict[str, str] = {}
    for key, value in metadata.items():
        if len(cleaned) >= 16:
            break
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if 1 <= len(key) <= 256 and len(value) <= 256:
            cleaned[key] = value
    return cleaned or None


def _normalize_output_content(content: Any) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        return []
    output: list[dict[str, Any]] = []
    for block in content:
        if "text" in block:
            output.append({"type": "text", "text": block["text"]})
        elif "toolUse" in block:
            tool_use = block["toolUse"]
            output.append(
                {
                    "type": "tool_use",
                    "id": tool_use.get("toolUseId"),
                    "name": tool_use.get("name"),
                    "input": tool_use.get("input", {}),
                }
            )
        elif "toolResult" in block:
            tool_result = block["toolResult"]
            output.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_result.get("toolUseId"),
                    "content": _normalize_tool_result_output_content(tool_result.get("content")),
                    "is_error": tool_result.get("status") == "error",
                }
            )
    return output


def _normalize_stop_reason(stop_reason: Any) -> str | None:
    if isinstance(stop_reason, str):
        return stop_reason
    return None


async def _convert_converse_event(
    event: dict[str, Any],
    state: StreamState,
    model: str,
) -> AsyncIterator[dict[str, Any]]:
    if "messageStart" in event and not state.message_started:
        state.message_started = True
        yield {
            "type": "message_start",
            "message": {
                "id": state.message_id,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": model,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        }
        return

    if "contentBlockStart" in event:
        start_event = event["contentBlockStart"]
        index = start_event.get("contentBlockIndex", 0)
        start = start_event.get("start", {})
        content_block = _map_content_block_start(start)
        if content_block:
            yield {
                "type": "content_block_start",
                "index": index,
                "content_block": content_block,
            }
        return

    if "contentBlockDelta" in event:
        delta_event = event["contentBlockDelta"]
        index = delta_event.get("contentBlockIndex", 0)
        delta = delta_event.get("delta", {})
        delta_payload = _map_content_block_delta(delta)
        if delta_payload:
            yield {
                "type": "content_block_delta",
                "index": index,
                "delta": delta_payload,
            }
        return

    if "contentBlockStop" in event:
        stop_event = event["contentBlockStop"]
        yield {"type": "content_block_stop", "index": stop_event.get("contentBlockIndex", 0)}
        return

    if "messageStop" in event:
        stop_reason = event["messageStop"].get("stopReason")
        state.stop_reason = _normalize_stop_reason(stop_reason)
        if state.usage is not None:
            async for payload in _flush_message_delta(state):
                yield payload
            yield {"type": "message_stop"}
            state.message_stopped = True
        return

    if "metadata" in event:
        metadata = event["metadata"]
        usage = metadata.get("usage", {})
        state.usage = usage
        if state.stop_reason is not None:
            async for payload in _flush_message_delta(state):
                yield payload
            yield {"type": "message_stop"}
            state.message_stopped = True
        return


async def _flush_message_delta(state: StreamState) -> AsyncIterator[dict[str, Any]]:
    if state.stop_reason is None and not state.usage:
        return
    usage = state.usage or {}
    yield {
        "type": "message_delta",
        "delta": {"stop_reason": state.stop_reason, "stop_sequence": None},
        "usage": {
            "output_tokens": usage.get("outputTokens", 0),
            "cache_read_input_tokens": usage.get("cacheReadInputTokens"),
            "cache_creation_input_tokens": usage.get("cacheCreationInputTokens"),
        },
    }
    state.stop_reason = None
    state.usage = None


def _map_content_block_start(start: dict[str, Any]) -> dict[str, Any] | None:
    if "text" in start:
        return {"type": "text", "text": ""}
    if "toolUse" in start:
        tool = start["toolUse"]
        return {
            "type": "tool_use",
            "id": tool.get("toolUseId"),
            "name": tool.get("name"),
            "input": {},
        }
    return None


def _map_content_block_delta(delta: dict[str, Any]) -> dict[str, Any] | None:
    if "text" in delta:
        return {"type": "text_delta", "text": delta["text"]}
    if "toolUse" in delta:
        return {"type": "input_json_delta", "partial_json": delta["toolUse"].get("input", "")}
    return None


def _to_sse(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode()
