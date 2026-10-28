"""Hevy access for the studio, via the hosted hevy-mcp server.

The server is https://mcp.hevy-mcp.dev/mcp. The Hevy API key is sent as a
bearer token and is never logged. Tool definitions are cached briefly; each
chat turn still opens its own short MCP session.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger("studio.hevy")

DEFAULT_URL = "https://mcp.hevy-mcp.dev/mcp"
PROTOCOL_VERSIONS = ("2025-03-26", "2024-11-05")
TOOL_CACHE_SECONDS = 600
RESULT_LIMIT = 14_000
SKIPPED_TOOLS = {"feedback"}

_cache_lock = threading.Lock()
_cached_tools: list[dict[str, Any]] | None = None
_cached_at = 0.0


def configured() -> bool:
    return bool(os.getenv("HEVY_API_KEY", "").strip())


def tool_specs() -> list[dict[str, Any]]:
    """OpenAI responses-API function tools, or an empty list when Hevy is off."""
    global _cached_tools, _cached_at
    if not configured():
        return []
    now = time.time()
    with _cache_lock:
        if _cached_tools is not None and now - _cached_at < TOOL_CACHE_SECONDS:
            return list(_cached_tools)
    try:
        with _Session() as session:
            tools = session.list_tools()
    except Exception:
        logger.exception("Could not load Hevy tools")
        raise
    specs = [_spec(tool) for tool in tools if tool.get("name") not in SKIPPED_TOOLS]
    with _cache_lock:
        _cached_tools = specs
        _cached_at = time.time()
    return list(specs)


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    try:
        with _Session() as session:
            result = session.call_tool(name, arguments)
    except Exception:
        logger.exception("Hevy tool %s failed", name)
        return "Hevy could not complete that request."
    return _result_text(result)


def _spec(tool: dict[str, Any]) -> dict[str, Any]:
    parameters = tool.get("inputSchema")
    if not isinstance(parameters, dict):
        parameters = {"type": "object", "properties": {}}
    return {
        "type": "function",
        "name": str(tool.get("name") or "hevy"),
        "description": str(tool.get("description") or "")[:2000],
        "parameters": parameters,
    }


def _result_text(result: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in result.get("content") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and item.get("text"):
            parts.append(str(item["text"]))
        elif item.get("type") == "resource" and isinstance(item.get("resource"), dict):
            resource = item["resource"]
            text = resource.get("text")
            if text:
                parts.append(str(text))
    text = "\n".join(parts).strip()
    if not text:
        text = "Hevy returned no content."
    if result.get("isError"):
        text = "Hevy tool error: " + text
    if len(text) > RESULT_LIMIT:
        text = text[:RESULT_LIMIT] + "\n…truncated"
    return text


def _mcp_messages(response: httpx.Response) -> list[dict[str, Any]]:
    content_type = response.headers.get("content-type", "")
    body = response.text.strip()
    if not body:
        return []
    if "text/event-stream" in content_type:
        messages: list[dict[str, Any]] = []
        for line in body.splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                messages.append(parsed)
        return messages
    parsed = response.json()
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        return [parsed]
    return []


class _Session:
    def __init__(self) -> None:
        self.url = (os.getenv("HEVY_MCP_URL") or DEFAULT_URL).strip() or DEFAULT_URL
        self.api_key = os.getenv("HEVY_API_KEY", "").strip()
        self.protocol = PROTOCOL_VERSIONS[0]
        self.session_id = ""
        self._id = 0
        self.client = httpx.Client(timeout=70)

    def __enter__(self) -> "_Session":
        self._initialize()
        return self

    def __exit__(self, *_args: object) -> None:
        self.client.close()

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._rpc("tools/list")
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list):
            return []
        return [tool for tool in tools if isinstance(tool, dict)]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        return result if isinstance(result, dict) else {}

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.protocol,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def _initialize(self) -> None:
        last_error = "Hevy MCP did not accept the session."
        for version in PROTOCOL_VERSIONS:
            self.protocol = version
            try:
                result = self._rpc(
                    "initialize",
                    {
                        "protocolVersion": version,
                        "capabilities": {},
                        "clientInfo": {"name": "fergus-studio", "version": "1"},
                    },
                )
            except RuntimeError as exc:
                last_error = str(exc)
                continue
            if isinstance(result, dict) and result.get("protocolVersion"):
                self.protocol = str(result["protocolVersion"])
            self._rpc("notifications/initialized", notify=True)
            return
        raise RuntimeError(last_error)

    def _rpc(self, method: str, params: dict[str, Any] | None = None, *, notify: bool = False) -> Any:
        body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        request_id = None
        if not notify:
            self._id += 1
            request_id = self._id
            body["id"] = request_id
        response = self.client.post(self.url, headers=self._headers(), json=body)
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            self.session_id = session_id
        if response.status_code == 401:
            raise RuntimeError("Hevy rejected the API key.")
        if response.status_code >= 400:
            raise RuntimeError(f"Hevy MCP returned {response.status_code}.")
        messages = _mcp_messages(response)
        if notify:
            return None
        for message in messages:
            if message.get("id") != request_id:
                continue
            if message.get("error"):
                error = message["error"]
                detail = error.get("message") if isinstance(error, dict) else str(error)
                raise RuntimeError(detail or "Hevy MCP request failed.")
            return message.get("result")
        if messages and messages[-1].get("error"):
            error = messages[-1]["error"]
            detail = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(detail or "Hevy MCP request failed.")
        return messages[-1].get("result") if messages else {}
