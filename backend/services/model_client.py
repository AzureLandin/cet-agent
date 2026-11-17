from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI
from services.http_client import create_httpx_client


def extract_message_text(content: Any) -> str:
    """Normalize string or content-block list returned by LangChain messages into plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


def to_langchain_messages(messages: list[dict]) -> list[BaseMessage]:
    """Convert OpenAI-style message dicts into LangChain BaseMessage objects."""
    converted: list[BaseMessage] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "system":
            converted.append(SystemMessage(content=content or ""))
        elif role == "user":
            converted.append(HumanMessage(content=content or ""))
        elif role == "assistant":
            raw_tcs = msg.get("tool_calls") or []
            lc_tcs = []
            for idx, tc in enumerate(raw_tcs):
                fn = tc.get("function") or {}
                raw_args = fn.get("arguments") or "{}"
                try:
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    if not isinstance(parsed_args, dict):
                        parsed_args = {}
                except (ValueError, TypeError):
                    parsed_args = {}
                lc_tcs.append(
                    {
                        "id": tc.get("id") or f"call_{idx}",
                        "name": fn.get("name") or "",
                        "args": parsed_args,
                        "type": "tool_call",
                    }
                )
            converted.append(AIMessage(content=content or "", tool_calls=lc_tcs))
        elif role == "tool":
            converted.append(
                ToolMessage(
                    content=content or "",
                    tool_call_id=msg.get("tool_call_id") or "",
                )
            )
    return converted


class _RobustChatOpenAI(ChatOpenAI):
    """ChatOpenAI tuned for OpenAI-compatible gateways with non-standard tool_call deltas."""

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        choices = chunk.get("choices") or []
        if choices and isinstance(choices[0], dict):
            delta = choices[0].get("delta")
            if isinstance(delta, dict) and isinstance(delta.get("tool_calls"), list):
                normalized_tcs = []
                for rtc in delta["tool_calls"]:
                    if isinstance(rtc, dict) and "index" not in rtc:
                        rtc = {**rtc, "index": None}
                    normalized_tcs.append(rtc)
                choices[0] = {**choices[0], "delta": {**delta, "tool_calls": normalized_tcs}}
                chunk = {**chunk, "choices": choices}

        return super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )


class ModelClient:
    def __init__(self, config: dict):
        self.base_url = config["base_url"]
        self.api_key = config["api_key"]
        self.model = config["model"]
        self.http_client = create_httpx_client()
        self.chat_model: ChatOpenAI = _RobustChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=self.http_client,
            http_socket_options=(),
            use_responses_api=False,
            max_retries=2,
            streaming=True,
        )
        self.client = self.chat_model.root_client

    def get_chat_model(self) -> ChatOpenAI:
        return self.chat_model

    def chat_completion(self, messages: list[dict], response_format: dict | None = None) -> str:
        runnable = self.chat_model
        if response_format is not None:
            runnable = runnable.bind(response_format=response_format)
        result = runnable.invoke(to_langchain_messages(messages))
        return extract_message_text(result.content)

    def chat_completion_stream(self, messages: list[dict]):
        for chunk in self.chat_model.stream(to_langchain_messages(messages)):
            text = extract_message_text(chunk.content)
            if text:
                yield text

    def chat_completion_stream_events(self, messages: list[dict], tools: list[dict] | None = None):
        runnable = self.chat_model.bind_tools(tools) if tools else self.chat_model
        acc: AIMessageChunk | None = None

        for chunk in runnable.stream(to_langchain_messages(messages)):
            if isinstance(chunk, AIMessageChunk):
                acc = chunk if acc is None else acc + chunk
            text = extract_message_text(chunk.content)
            if text:
                yield {"type": "token", "content": text}

        if acc is not None and (acc.tool_calls or acc.invalid_tool_calls):
            formatted: list[dict] = []
            for idx, tc in enumerate(acc.tool_calls):
                formatted.append(
                    {
                        "id": tc.get("id") or f"call_{idx}",
                        "name": tc.get("name") or "",
                        "arguments": json.dumps(tc.get("args") or {}, ensure_ascii=False),
                    }
                )
            for idx, itc in enumerate(acc.invalid_tool_calls, start=len(formatted)):
                formatted.append(
                    {
                        "id": itc.get("id") or f"call_{idx}",
                        "name": itc.get("name") or "",
                        "arguments": itc.get("args") or "{}",
                    }
                )
            if formatted:
                yield {"type": "tool_calls", "tool_calls": formatted}
