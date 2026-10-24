"""What a person may do through MCP, and the checks before anything is written.

- Usable tools: action tools (never read-only) that are on, on a server that is on, whose
  allowed roles include one of the person's roles (admins: all).
- Allowed projects: the GitLab projects the person can read through the GitLab connector's
  access mapping. An action may only target one of those.
- Every check runs twice: when GitMore proposes the action, and again when the person
  confirms, so a role or setting changed in between is respected.
"""

import json
import re
from dataclasses import dataclass, field

import psycopg

from app.auth import User

# Arguments that hold text written into the tool, where GitMore adds who asked for it.
TEXT_FIELDS = ("description", "body", "text")


@dataclass
class UsableTool:
    id: str
    server_name: str
    server_url: str
    auth_encrypted: str
    name: str
    description: str
    input_schema: dict


@dataclass
class Project:
    id: str
    path: str       # e.g. gitmore-demo-shreya/engineering
    name: str       # e.g. engineering
    web_url: str


@dataclass
class Scope:
    tools: list[UsableTool] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)

    def tool(self, name: str) -> UsableTool | None:
        return next((t for t in self.tools if t.name == name), None)


def scope_for(conn: psycopg.Connection, user: User) -> Scope:
    roles = list({*user.roles, "all"})
    tools = conn.execute(
        """
        SELECT t.id::text, s.name, s.url, s.auth_encrypted, t.name, t.description, t.input_schema
        FROM mcp_tools t JOIN mcp_servers s ON s.id = t.server_id
        WHERE t.enabled AND NOT t.read_only AND s.enabled AND s.auth_encrypted IS NOT NULL
          AND (%(admin)s OR t.allowed_roles && %(roles)s)
        ORDER BY t.name
        """,
        {"admin": user.is_admin, "roles": roles},
    ).fetchall()
    projects = conn.execute(
        """
        SELECT a.container_id, c.config->>'group', a.container_name, c.config->>'url'
        FROM source_access a JOIN connectors c ON c.id = a.connector_id
        WHERE c.kind = 'gitlab' AND c.enabled AND (%(admin)s OR a.allowed_roles && %(roles)s)
        ORDER BY a.container_name
        """,
        {"admin": user.is_admin, "roles": roles},
    ).fetchall()
    return Scope(
        tools=[UsableTool(*row) for row in tools],
        projects=[Project(id=pid, path=f"{group}/{name}", name=name,
                          web_url=f"{(url or 'https://gitlab.com').rstrip('/')}/{group}/{name}")
                  for pid, group, name, url in projects],
    )


class ActionRefused(Exception):
    """A reason the person can read, e.g. 'You can't act in the security project'."""


def check(scope: Scope, user: User, tool_name: str, arguments: dict) -> UsableTool:
    """Raise ActionRefused unless this person may run this tool with these arguments."""
    tool = scope.tool(tool_name)
    if not tool:
        raise ActionRefused(f"{tool_name} isn't turned on for your role.")
    if not isinstance(arguments, dict):
        raise ActionRefused("The action's details are malformed.")
    if arguments.get("group_id") and not user.is_admin:
        raise ActionRefused("Actions on a whole group are for admins only; pick a project.")
    target = str(arguments.get("project_id") or "").strip()
    url = str(arguments.get("url") or "").strip()
    if target:
        if not any(target in (p.id, p.path, p.name) for p in scope.projects):
            raise ActionRefused(f"You can't act in the project '{target}'.")
        arguments["project_id"] = next(p.id for p in scope.projects if target in (p.id, p.path, p.name))
    if url and not any(url == p.web_url or url.startswith(p.web_url + "/") for p in scope.projects):
        raise ActionRefused("That link isn't in a project you can access.")
    if not target and not url and not (user.is_admin and arguments.get("group_id")):
        raise ActionRefused("The action needs a project.")
    return tool


def sign(arguments: dict, user: User) -> dict:
    """Mark text written into the tool with who asked, since the server acts with the admin's token."""
    signed = dict(arguments)
    for key in TEXT_FIELDS:
        if isinstance(signed.get(key), str) and signed[key].strip():
            signed[key] = f"{signed[key].rstrip()}\n\n_Created with GitMore on behalf of {user.name}_"
            break
    return signed


def find_created_issue(conn: psycopg.Connection, project_id: str, title: str, since) -> str | None:
    """GitLab's MCP server sometimes errors while reading back an issue it did create. Ask the
    GitLab connector whether an issue with this title appeared since the action started."""
    from app.connectors.clients import ConnectorError, client
    from app.vault import decrypt

    row = conn.execute("SELECT token_encrypted, config FROM connectors WHERE kind = 'gitlab' AND enabled "
                       "ORDER BY created_at LIMIT 1").fetchone()
    if not row or not title:
        return None
    try:
        api = client("gitlab", decrypt(row[0]), row[1])
        issues, _ = api.get(f"/projects/{project_id}/issues?order_by=created_at&sort=desc&per_page=10"
                            f"&created_after={since.isoformat()}")
    except (ConnectorError, RuntimeError):
        return None
    match = next((i for i in issues if i.get("title", "").strip() == title.strip()), None)
    return match["web_url"] if match else None


URL = re.compile(r"https?://[^\s\"'<>)]+")


def result_link(text: str, data: dict | None) -> str | None:
    """The web link of what the tool created, when it says so."""
    for key in ("web_url", "webUrl", "url"):
        if isinstance(data, dict) and isinstance(data.get(key), str):
            return data[key]
    match = URL.search(text or "") or URL.search(json.dumps(data or {}))
    return match.group(0) if match else None
