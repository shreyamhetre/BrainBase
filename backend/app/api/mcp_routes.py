"""MCP servers and their tools.

Everyone sees which tools exist and which they can use. Admins connect a server with a
token (tested by listing its tools, then stored encrypted), refresh its tool list, turn
action tools on or off and choose which roles may use each one.
"""

from datetime import datetime
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, field_validator

from app.audit import record
from app.auth import User, admin_user, current_user
from app.db.connection import connect
from app.mcp_client import McpError, list_tools
from app.roles import content_roles
from app.vault import decrypt, encrypt, hint

router = APIRouter(tags=["mcp"])

DEFAULT_URLS = {"gitlab": "https://gitlab.com/api/v4/mcp", "slack": "https://mcp.slack.com/mcp"}


class McpToolOut(BaseModel):
    id: str
    name: str
    description: str
    read_only: bool
    enabled: bool
    allowed_roles: list[str]
    you_can_use: bool


class McpServerOut(BaseModel):
    id: str
    kind: str
    name: str
    url: str
    enabled: bool
    status: str
    last_error: str | None = None       # admin only
    last_checked_at: datetime | None
    token_hint: str | None = None       # admin only
    tools: list[McpToolOut]


class ServerIn(BaseModel):
    kind: str = Field(pattern="^(gitlab|slack|custom)$")
    name: str = Field(min_length=1, max_length=80)
    url: str | None = Field(default=None, max_length=300)
    token: str = Field(min_length=8, max_length=2000)

    @field_validator("url")
    @classmethod
    def https_only(cls, v: str | None) -> str | None:
        if v and not v.startswith(("https://", "http://localhost")):
            raise ValueError("Use an https:// URL")
        return v


class ServerEdit(BaseModel):
    enabled: bool | None = None
    token: str | None = Field(default=None, min_length=8, max_length=2000)


class ToolEdit(BaseModel):
    enabled: bool | None = None
    allowed_roles: list[str] | None = None


def _servers(conn: psycopg.Connection, user: User, server_id: str | None = None) -> list[McpServerOut]:
    servers = conn.execute(
        "SELECT id::text, kind, name, url, enabled, status, last_error, last_checked_at, auth_encrypted "
        "FROM mcp_servers WHERE (%s::uuid IS NULL OR id = %s::uuid) ORDER BY created_at", (server_id, server_id),
    ).fetchall()
    tools = conn.execute("SELECT id::text, server_id::text, name, description, read_only, enabled, allowed_roles "
                         "FROM mcp_tools ORDER BY read_only, name").fetchall()
    mine = set(user.roles) | {"all"}
    out = []
    for sid, kind, name, url, enabled, st, err, checked, auth in servers:
        server = McpServerOut(
            id=sid, kind=kind, name=name, url=url, enabled=enabled, status=st, last_checked_at=checked,
            tools=[McpToolOut(id=tid, name=tname, description=desc, read_only=ro, enabled=on, allowed_roles=roles,
                              you_can_use=enabled and on and not ro and (user.is_admin or bool(mine & set(roles))))
                   for tid, server_id_, tname, desc, ro, on, roles in tools if server_id_ == sid],
        )
        if user.is_admin:
            server.last_error = err
            try:
                server.token_hint = hint(decrypt(auth)) if auth else None
            except RuntimeError:
                server.token_hint = "can't decrypt"
        out.append(server)
    return out


def _one(conn, user: User, server_id: str) -> McpServerOut:
    found = _servers(conn, user, server_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such MCP server")
    return found[0]


def _store_tools(conn, server_id: str, tools) -> None:
    """Add new tools (off), update descriptions, drop tools the server no longer offers."""
    names = [t.name for t in tools]
    for t in tools:
        conn.execute(
            "INSERT INTO mcp_tools (server_id, name, description, input_schema, read_only) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (server_id, name) DO UPDATE SET description = EXCLUDED.description, "
            "input_schema = EXCLUDED.input_schema, read_only = EXCLUDED.read_only, "
            "enabled = mcp_tools.enabled AND NOT EXCLUDED.read_only",
            (server_id, t.name, t.description[:2000], Jsonb(t.input_schema), t.read_only),
        )
    conn.execute("DELETE FROM mcp_tools WHERE server_id = %s AND NOT (name = ANY(%s))", (server_id, names))


@router.get("/mcp", response_model=list[McpServerOut])
def list_servers(user: User = Depends(current_user)) -> list[McpServerOut]:
    with connect() as conn:
        return _servers(conn, user)


@router.post("/admin/mcp", response_model=McpServerOut, status_code=status.HTTP_201_CREATED)
def add_server(body: ServerIn, admin: User = Depends(admin_user)) -> McpServerOut:
    url = body.url or DEFAULT_URLS.get(body.kind)
    if not url:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A custom MCP server needs its URL")
    try:
        tools = list_tools(url, body.token)  # proves the token works before anything is saved
    except McpError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Couldn't connect: {e}") from None
    with connect() as conn:
        server_id = conn.execute(
            "INSERT INTO mcp_servers (kind, name, url, auth_encrypted, status, last_checked_at, created_by) "
            "VALUES (%s, %s, %s, %s, 'connected', now(), %s) RETURNING id::text",
            (body.kind, body.name.strip(), url, encrypt(body.token), admin.id),
        ).fetchone()[0]
        _store_tools(conn, server_id, tools)
        record(conn, admin.id, "mcp.added", name=body.name, tools=len(tools))
        return _one(conn, admin, server_id)


@router.post("/admin/mcp/{server_id}/refresh", response_model=McpServerOut)
def refresh_server(server_id: UUID, admin: User = Depends(admin_user)) -> McpServerOut:
    sid = str(server_id)
    with connect() as conn:
        row = conn.execute("SELECT url, auth_encrypted FROM mcp_servers WHERE id = %s", (sid,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such MCP server")
        try:
            _store_tools(conn, sid, list_tools(row[0], decrypt(row[1])))
            conn.execute("UPDATE mcp_servers SET status = 'connected', last_error = NULL, last_checked_at = now() "
                         "WHERE id = %s", (sid,))
        except (McpError, RuntimeError) as e:
            conn.execute("UPDATE mcp_servers SET status = 'error', last_error = %s, last_checked_at = now() "
                         "WHERE id = %s", (str(e), sid))
        return _one(conn, admin, sid)


@router.patch("/admin/mcp/{server_id}", response_model=McpServerOut)
def edit_server(server_id: UUID, body: ServerEdit, admin: User = Depends(admin_user)) -> McpServerOut:
    sid = str(server_id)
    with connect() as conn:
        row = conn.execute("SELECT name, url FROM mcp_servers WHERE id = %s", (sid,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such MCP server")
        if body.token:
            try:
                tools = list_tools(row[1], body.token)
            except McpError as e:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"The new token doesn't work: {e}") from None
            conn.execute("UPDATE mcp_servers SET auth_encrypted = %s, status = 'connected', last_error = NULL, "
                         "last_checked_at = now() WHERE id = %s", (encrypt(body.token), sid))
            _store_tools(conn, sid, tools)
        if body.enabled is not None:
            conn.execute("UPDATE mcp_servers SET enabled = %s WHERE id = %s", (body.enabled, sid))
        record(conn, admin.id, "mcp.updated", name=row[0],
               changed=[k for k in ("token", "enabled") if getattr(body, k) is not None])
        return _one(conn, admin, sid)


@router.delete("/admin/mcp/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_server(server_id: UUID, admin: User = Depends(admin_user)) -> None:
    with connect() as conn:
        row = conn.execute("DELETE FROM mcp_servers WHERE id = %s RETURNING name", (str(server_id),)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such MCP server")
        record(conn, admin.id, "mcp.removed", name=row[0])


@router.patch("/admin/mcp/tools/{tool_id}", response_model=McpServerOut)
def edit_tool(tool_id: UUID, body: ToolEdit, admin: User = Depends(admin_user)) -> McpServerOut:
    with connect() as conn:
        row = conn.execute("SELECT t.server_id::text, t.name, t.read_only, s.name FROM mcp_tools t "
                           "JOIN mcp_servers s ON s.id = t.server_id WHERE t.id = %s", (str(tool_id),)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such tool")
        server_id, tool, read_only, server = row
        if body.enabled and read_only:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Read-only tools stay off: GitMore reads from the permission-filtered index instead")
        if body.allowed_roles is not None:
            unknown = set(body.allowed_roles) - set(content_roles(conn)) - {"all"}
            if unknown:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown roles: {sorted(unknown)}")
            roles = ["all"] if "all" in body.allowed_roles else sorted(set(body.allowed_roles))
            conn.execute("UPDATE mcp_tools SET allowed_roles = %s WHERE id = %s", (roles, str(tool_id)))
            record(conn, admin.id, "mcp.tool_roles", name=f"{server} · {tool}", after=roles)
        if body.enabled is not None:
            conn.execute("UPDATE mcp_tools SET enabled = %s WHERE id = %s", (body.enabled, str(tool_id)))
            record(conn, admin.id, "mcp.tool_on" if body.enabled else "mcp.tool_off", name=f"{server} · {tool}")
        return _one(conn, admin, server_id)
