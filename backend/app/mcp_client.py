"""Talk to MCP servers (the official GitLab and Slack ones) over Streamable HTTP.

Each call opens a short session: connect with the stored token, do one thing, close.
That is plenty for admin actions and confirmed user actions, and nothing stays open.

Uses the official MCP Python SDK (package `mcp`).
"""

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

import httpx2
from mcp import Client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

TIMEOUT = httpx2.Timeout(30.0)


class McpError(Exception):
    """A message an admin can act on, e.g. '403 Forbidden: token needs the MCP permission'."""


@dataclass
class ToolInfo:
    name: str
    description: str
    input_schema: dict
    read_only: bool   # from the tool's annotations; read-only tools are never enabled in GitMore


@dataclass
class ToolResult:
    ok: bool
    text: str
    data: dict | None


async def _session(url: str, token: str, work):
    http = create_mcp_http_client(headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    async with http:
        async with Client(streamable_http_client(url, http_client=http), cache=None) as client:
            return await work(client)


def _run(url: str, token: str, work):
    try:
        return asyncio.run(_session(url, token, work))
    except McpError:
        raise
    except Exception as e:  # network, auth, protocol: one readable message for the admin
        raise McpError(_probe(url, token) or _explain(e)) from None


def _explain(e: Exception) -> str:
    # anyio wraps transport failures in exception groups; show the innermost cause
    while isinstance(e, BaseExceptionGroup) and e.exceptions:
        e = e.exceptions[0]
    return str(e) or type(e).__name__


def _probe(url: str, token: str) -> str | None:
    """The SDK hides HTTP status codes; one plain request tells the admin what to fix."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "gitmore", "version": "1"}}}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"})
    try:
        urllib.request.urlopen(req, timeout=20).close()
        return None
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return ("The server rejected the token (401). For GitLab, use a fine-grained personal access token "
                    "with the Duo permission 'MCP tool: Execute'; classic, project and group tokens don't work.")
        if e.code == 403:
            return ("The token works but isn't allowed to use MCP here (403). Check the token's MCP tool permission "
                    "and that the group allows MCP client access.")
        body = e.read().decode(errors="replace")
        try:  # JSON-RPC errors carry a readable message, often with a link to fix it
            body = json.loads(body).get("error", {}).get("message") or body
        except (ValueError, AttributeError):
            pass
        return f"The server answered HTTP {e.code}: {body[:600]}"
    except urllib.error.URLError as e:
        return f"Can't reach {url}: {e.reason}"


def _schema(tool) -> dict:
    return getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {}


def _read_only(tool) -> bool:
    annotations = getattr(tool, "annotations", None)
    hint = getattr(annotations, "read_only_hint", None)
    if hint is None:
        hint = getattr(annotations, "readOnlyHint", None)
    return bool(hint)


def list_tools(url: str, token: str) -> list[ToolInfo]:
    async def work(client):
        result = await client.list_tools()
        return [ToolInfo(t.name, t.description or "", _schema(t), _read_only(t)) for t in result.tools]
    return _run(url, token, work)


def call_tool(url: str, token: str, name: str, arguments: dict) -> ToolResult:
    async def work(client):
        result = await client.call_tool(name, arguments)
        text = "\n".join(getattr(block, "text", "") for block in (result.content or []) if getattr(block, "text", ""))
        data = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
        is_error = bool(getattr(result, "is_error", None) or getattr(result, "isError", None))
        return ToolResult(ok=not is_error, text=text, data=data)
    return _run(url, token, work)
