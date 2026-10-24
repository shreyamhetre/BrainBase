"""Settings managed in the app: roles, connectors and access mapping (MCP tools: mcp_routes.py).

Everyone logged in can see what is connected and what they can read or use.
Only admins change anything. Tokens go in encrypted and never come back out.
"""

from datetime import datetime
from uuid import UUID

import psycopg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, field_validator

from app.audit import record
from app.auth import User, admin_user, current_user
from app.connectors.clients import ConnectorError, client
from app.connectors.sync import run_sync
from app.ingestion.store import ADMINS_ONLY
from app.db.connection import connect
from app.roles import content_roles
from app.vault import decrypt, encrypt, hint

router = APIRouter(tags=["settings"])


# ---------- roles ----------

class RoleOut(BaseModel):
    name: str
    description: str


class RoleAdminOut(RoleOut):
    users: int
    sources: int
    created_at: datetime


class RoleIn(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,30}$", description="lowercase, e.g. finance or legal")
    description: str = Field(default="", max_length=200)


class RoleEdit(BaseModel):
    description: str = Field(max_length=200)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(_: User = Depends(current_user)) -> list[RoleOut]:
    with connect() as conn:
        rows = conn.execute("SELECT name, description FROM roles ORDER BY name").fetchall()
    return [RoleOut(name=n, description=d) for n, d in rows]


ROLE_ADMIN_SQL = """
SELECT r.name, r.description,
       (SELECT count(*) FROM users u WHERE r.name = ANY(u.roles) AND NOT u.is_admin),
       (SELECT count(*) FROM source_access s WHERE r.name = ANY(s.allowed_roles)),
       r.created_at
FROM roles r
"""


def _role_admin(row) -> RoleAdminOut:
    return RoleAdminOut(**dict(zip(RoleAdminOut.model_fields, row)))


@router.get("/admin/roles", response_model=list[RoleAdminOut])
def admin_roles(_: User = Depends(admin_user)) -> list[RoleAdminOut]:
    with connect() as conn:
        return [_role_admin(row) for row in conn.execute(f"{ROLE_ADMIN_SQL} ORDER BY r.name")]


@router.post("/admin/roles", response_model=RoleAdminOut, status_code=status.HTTP_201_CREATED)
def add_role(body: RoleIn, admin: User = Depends(admin_user)) -> RoleAdminOut:
    if body.name in ("all", ADMINS_ONLY):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"'{body.name}' is reserved")
    try:
        with connect() as conn:
            conn.execute("INSERT INTO roles (name, description) VALUES (%s, %s)", (body.name, body.description.strip()))
            record(conn, admin.id, "role.added", role=body.name)
            return _role_admin(conn.execute(f"{ROLE_ADMIN_SQL} WHERE r.name = %s", (body.name,)).fetchone())
    except UniqueViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The {body.name} role already exists") from None


@router.patch("/admin/roles/{name}", response_model=RoleAdminOut)
def edit_role(name: str, body: RoleEdit, admin: User = Depends(admin_user)) -> RoleAdminOut:
    with connect() as conn:
        if not conn.execute("UPDATE roles SET description = %s WHERE name = %s RETURNING name",
                            (body.description.strip(), name)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such role")
        return _role_admin(conn.execute(f"{ROLE_ADMIN_SQL} WHERE r.name = %s", (name,)).fetchone())


@router.delete("/admin/roles/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(name: str, admin: User = Depends(admin_user)) -> None:
    with connect() as conn:
        row = conn.execute(f"{ROLE_ADMIN_SQL} WHERE r.name = %s", (name,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such role")
        role = _role_admin(row)
        if role.users or role.sources:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"{name} is still used by {role.users} people and {role.sources} sources; remove it from them first")
        conn.execute("DELETE FROM roles WHERE name = %s", (name,))
        conn.execute("UPDATE access_requests SET status = 'cancelled', decided_at = now() "
                     "WHERE role = %s AND status = 'pending'", (name,))
        record(conn, admin.id, "role.removed", role=name)


# ---------- connectors ----------

class ConnectorOut(BaseModel):
    id: str
    kind: str
    name: str
    enabled: bool
    status: str
    last_error: str | None
    last_checked_at: datetime | None
    last_sync_at: datetime | None
    sync_interval_minutes: int
    sources: int
    unmapped: int
    you_can_read: list[str]
    documents: int
    syncing: bool
    last_run: dict | None
    # Admin only
    config: dict | None = None
    token_hint: str | None = None


class AccessOut(BaseModel):
    id: str
    container_id: str
    container_name: str
    container_kind: str
    allowed_roles: list[str]
    discovered_at: datetime


class ConnectorIn(BaseModel):
    kind: str = Field(pattern="^(slack|gitlab)$")
    name: str = Field(min_length=1, max_length=80)
    token: str = Field(min_length=8, max_length=500)
    url: str | None = Field(default=None, max_length=200)      # GitLab only
    group: str | None = Field(default=None, max_length=200)    # GitLab only

    @field_validator("url")
    @classmethod
    def https_only(cls, v: str | None) -> str | None:
        if v and not v.startswith(("https://", "http://localhost")):
            raise ValueError("Use an https:// URL")
        return v.rstrip("/") if v else v


class ConnectorEdit(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    sync_interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    token: str | None = Field(default=None, min_length=8, max_length=500)


class AccessEdit(BaseModel):
    allowed_roles: list[str]


CONNECTOR_SQL = """
SELECT c.id::text, c.kind, c.name, c.enabled, c.status, c.last_error, c.last_checked_at, c.last_sync_at,
       c.sync_interval_minutes, c.config, c.token_encrypted,
       count(s.id), count(s.id) FILTER (WHERE s.allowed_roles = '{}'),
       coalesce(array_agg(s.container_name ORDER BY s.container_name)
                FILTER (WHERE s.allowed_roles && %(roles)s), '{}'),
       (SELECT count(*) FROM documents d JOIN source_access a ON a.id = d.access_id WHERE a.connector_id = c.id),
       (SELECT to_jsonb(r) FROM (SELECT status, trigger, started_at, finished_at, seen, changed, deleted, chunks, error
                                 FROM sync_runs WHERE connector_id = c.id ORDER BY started_at DESC LIMIT 1) r)
FROM connectors c
LEFT JOIN source_access s ON s.connector_id = c.id
"""


def _connectors(conn: psycopg.Connection, user: User, where: str = "", params: dict | None = None) -> list[ConnectorOut]:
    # Admins read everything, including sources nobody has mapped yet
    roles = ["all", *user.roles]
    sql = CONNECTOR_SQL.replace("s.allowed_roles && %(roles)s", "true") if user.is_admin else CONNECTOR_SQL
    rows = conn.execute(f"{sql} {where} GROUP BY c.id ORDER BY c.created_at", {"roles": roles, **(params or {})}).fetchall()
    out = []
    for (cid, kind, name, enabled, st, err, checked, synced, interval, config, token, total, unmapped, readable,
         documents, last_run) in rows:
        item = ConnectorOut(id=cid, kind=kind, name=name, enabled=enabled, status=st, last_error=err if user.is_admin else None,
                            last_checked_at=checked, last_sync_at=synced, sync_interval_minutes=interval,
                            sources=total, unmapped=unmapped, you_can_read=readable, documents=documents,
                            syncing=bool(last_run and last_run["status"] == "running"),
                            last_run=last_run if user.is_admin else None)
        if user.is_admin:
            item.config = config
            try:
                item.token_hint = hint(decrypt(token))
            except RuntimeError:
                item.token_hint = "can't decrypt"
        out.append(item)
    return out


def _one(conn: psycopg.Connection, user: User, connector_id: str) -> ConnectorOut:
    found = _connectors(conn, user, "WHERE c.id = %(cid)s", {"cid": connector_id})
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such connector")
    return found[0]


def _discover(conn: psycopg.Connection, connector_id: str, kind: str, token: str, config: dict) -> int:
    """Upsert the channels or projects the token can see. New ones get no roles (admins only)."""
    containers = client(kind, token, config).containers()
    for c in containers:
        conn.execute(
            "INSERT INTO source_access (connector_id, container_id, container_name, container_kind) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (connector_id, container_id) "
            "DO UPDATE SET container_name = EXCLUDED.container_name, container_kind = EXCLUDED.container_kind",
            (connector_id, c.id, c.name, c.kind),
        )
    return len(containers)


@router.get("/connectors", response_model=list[ConnectorOut])
def list_connectors(user: User = Depends(current_user)) -> list[ConnectorOut]:
    with connect() as conn:
        return _connectors(conn, user)


@router.post("/admin/connectors", response_model=ConnectorOut, status_code=status.HTTP_201_CREATED)
def add_connector(body: ConnectorIn, admin: User = Depends(admin_user)) -> ConnectorOut:
    config = {"url": body.url, "group": body.group} if body.kind == "gitlab" else {}
    try:
        api = client(body.kind, body.token, config)
        config |= api.check()   # proves the token works before anything is saved
    except ConnectorError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Couldn't connect: {e}") from None

    with connect() as conn:
        connector_id = conn.execute(
            "INSERT INTO connectors (kind, name, config, token_encrypted, created_by, last_checked_at) "
            "VALUES (%s, %s, %s, %s, %s, now()) RETURNING id::text",
            (body.kind, body.name.strip(), Jsonb(config), encrypt(body.token), admin.id),
        ).fetchone()[0]
        found = _discover(conn, connector_id, body.kind, body.token, config)
        record(conn, admin.id, "connector.added", name=body.name, kind=body.kind, sources=found)
        return _one(conn, admin, connector_id)


@router.patch("/admin/connectors/{connector_id}", response_model=ConnectorOut)
def edit_connector(connector_id: UUID, body: ConnectorEdit, admin: User = Depends(admin_user)) -> ConnectorOut:
    cid = str(connector_id)
    with connect() as conn:
        row = conn.execute("SELECT kind, name, config FROM connectors WHERE id = %s", (cid,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such connector")
        kind, name, config = row
        changes: dict = {k: v for k, v in body.model_dump(exclude={"token"}).items() if v is not None}
        if body.token:
            try:
                client(kind, body.token, config).check()
            except ConnectorError as e:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"The new token doesn't work: {e}") from None
            changes |= {"token_encrypted": encrypt(body.token), "status": "connected", "last_error": None}
        if not changes:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update")
        sets = ", ".join(f"{k} = %({k})s" for k in changes)
        conn.execute(f"UPDATE connectors SET {sets} WHERE id = %(id)s", {**changes, "id": cid})
        record(conn, admin.id, "connector.updated", name=name,
               changed=sorted("token" if k == "token_encrypted" else k for k in changes if k not in ("status", "last_error")))
        return _one(conn, admin, cid)


@router.delete("/admin/connectors/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_connector(connector_id: UUID, admin: User = Depends(admin_user)) -> None:
    with connect() as conn:
        row = conn.execute("DELETE FROM connectors WHERE id = %s RETURNING name", (str(connector_id),)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such connector")
        record(conn, admin.id, "connector.removed", name=row[0])


@router.post("/admin/connectors/{connector_id}/check", response_model=ConnectorOut)
def check_connector(connector_id: UUID, admin: User = Depends(admin_user)) -> ConnectorOut:
    """Test the stored token and refresh the list of channels or projects."""
    cid = str(connector_id)
    with connect() as conn:
        row = conn.execute("SELECT kind, config, token_encrypted FROM connectors WHERE id = %s", (cid,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such connector")
        kind, config, token = row
        try:
            plain = decrypt(token)
            client(kind, plain, config).check()
            _discover(conn, cid, kind, plain, config)
            conn.execute("UPDATE connectors SET status = 'connected', last_error = NULL, last_checked_at = now() "
                         "WHERE id = %s", (cid,))
        except (ConnectorError, RuntimeError) as e:
            conn.execute("UPDATE connectors SET status = 'error', last_error = %s, last_checked_at = now() "
                         "WHERE id = %s", (str(e), cid))
        return _one(conn, admin, cid)


@router.post("/admin/connectors/{connector_id}/sync", status_code=status.HTTP_202_ACCEPTED)
def sync_now(connector_id: UUID, background: BackgroundTasks, admin: User = Depends(admin_user)) -> dict:
    """Start a sync in the background; the Connectors page polls for the result."""
    with connect() as conn:
        name = conn.execute("SELECT name FROM connectors WHERE id = %s", (str(connector_id),)).fetchone()
        if not name:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such connector")
        record(conn, admin.id, "connector.synced", name=name[0])
    background.add_task(run_sync, str(connector_id), "manual")
    return {"started": True}


@router.get("/admin/connectors/{connector_id}/access", response_model=list[AccessOut])
def connector_access(connector_id: UUID, _: User = Depends(admin_user)) -> list[AccessOut]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id::text, container_id, container_name, container_kind, allowed_roles, discovered_at "
            "FROM source_access WHERE connector_id = %s ORDER BY container_name", (str(connector_id),),
        ).fetchall()
    return [AccessOut(**dict(zip(AccessOut.model_fields, row))) for row in rows]


@router.patch("/admin/access/{access_id}", response_model=AccessOut)
def edit_access(access_id: UUID, body: AccessEdit, admin: User = Depends(admin_user)) -> AccessOut:
    wanted = sorted(set(body.allowed_roles))
    with connect() as conn:
        unknown = set(wanted) - set(content_roles(conn)) - {"all"}
        if unknown:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown roles: {sorted(unknown)}")
        if "all" in wanted:
            wanted = ["all"]   # everyone already includes every role
        before = conn.execute("SELECT container_name, allowed_roles FROM source_access WHERE id = %s",
                              (str(access_id),)).fetchone()
        if not before:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such channel or project")
        row = conn.execute(
            "UPDATE source_access SET allowed_roles = %s, updated_at = now() WHERE id = %s "
            "RETURNING id::text, container_id, container_name, container_kind, allowed_roles, discovered_at",
            (wanted, str(access_id)),
        ).fetchone()
        if sorted(before[1]) != wanted:
            # Content already indexed from here follows the new access straight away
            effective = wanted or [ADMINS_ONLY]
            conn.execute("UPDATE documents SET allowed_roles = %s WHERE access_id = %s", (effective, str(access_id)))
            conn.execute("UPDATE chunks c SET allowed_roles = %s FROM documents d "
                         "WHERE c.document_id = d.id AND d.access_id = %s", (effective, str(access_id)))
            record(conn, admin.id, "access.changed", source=before[0], before=sorted(before[1]), after=wanted)
    return AccessOut(**dict(zip(AccessOut.model_fields, row)))

