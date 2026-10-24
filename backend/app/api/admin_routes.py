"""Admin console endpoints: overview, users and roles, access requests and the activity log."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.audit import record
from app.auth import User, admin_user
from app.config import CONTENT_ROLES
from app.db.connection import connect

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_USER_COLUMNS = ("id::text, email, name, roles, is_admin, is_active, team, title, "
                      "last_login_at, created_at")


class AdminUserOut(BaseModel):
    id: str
    email: str
    name: str
    roles: list[str]
    is_admin: bool
    is_active: bool
    team: str | None
    title: str | None
    last_login_at: datetime | None
    created_at: datetime


class UserUpdate(BaseModel):
    roles: list[str] | None = None
    is_admin: bool | None = None
    is_active: bool | None = None


class Overview(BaseModel):
    users: int
    active: int
    inactive: int
    pending_requests: int
    active_last_7_days: int
    role_counts: dict[str, int]


class AccessRequestOut(BaseModel):
    id: str
    user_id: str
    user_name: str
    user_email: str
    user_team: str | None
    user_roles: list[str]
    role: str
    reason: str
    status: str
    note: str | None
    decided_by: str | None
    decided_at: datetime | None
    created_at: datetime


class Decision(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)


class ActivityOut(BaseModel):
    id: int
    actor: str | None
    action: str
    target: str | None
    details: dict
    created_at: datetime


def _user_out(row) -> AdminUserOut:
    return AdminUserOut(**dict(zip(AdminUserOut.model_fields, row)))


@router.get("/roles")
def roles(_: User = Depends(admin_user)) -> list[str]:
    return list(CONTENT_ROLES)


@router.get("/overview", response_model=Overview)
def overview(_: User = Depends(admin_user)) -> Overview:
    with connect() as conn:
        users, active, recent = conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE is_active), "
            "count(*) FILTER (WHERE last_login_at > now() - interval '7 days') FROM users"
        ).fetchone()
        pending = conn.execute("SELECT count(*) FROM access_requests WHERE status = 'pending'").fetchone()[0]
        counts = dict(conn.execute(
            "SELECT role, count(*) FROM users, unnest(roles) AS role "
            "WHERE is_active AND NOT is_admin GROUP BY role"
        ).fetchall())
    return Overview(users=users, active=active, inactive=users - active, pending_requests=pending,
                    active_last_7_days=recent, role_counts={r: counts.get(r, 0) for r in CONTENT_ROLES})


@router.get("/users", response_model=list[AdminUserOut])
def list_users(_: User = Depends(admin_user)) -> list[AdminUserOut]:
    with connect() as conn:
        rows = conn.execute(f"SELECT {ADMIN_USER_COLUMNS} FROM users ORDER BY is_admin DESC, name").fetchall()
    return [_user_out(row) for row in rows]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: UUID, body: UserUpdate, admin: User = Depends(admin_user)) -> AdminUserOut:
    user_id = str(user_id)
    if body.roles is not None:
        unknown = set(body.roles) - set(CONTENT_ROLES)
        if unknown:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown roles: {sorted(unknown)}")
    if user_id == admin.id and (body.is_admin is False or body.is_active is False):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't remove your own admin access")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if body.roles is not None:
        updates["roles"] = sorted(set(body.roles))
    if not updates:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nothing to update")

    assignments = ", ".join(f"{column} = %({column})s" for column in updates)
    with connect() as conn:
        before = conn.execute("SELECT roles, is_admin, is_active FROM users WHERE id = %s", (user_id,)).fetchone()
        if not before:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        row = conn.execute(
            f"UPDATE users SET {assignments} WHERE id = %(id)s RETURNING {ADMIN_USER_COLUMNS}",
            {**updates, "id": user_id},
        ).fetchone()
        if "roles" in updates and updates["roles"] != sorted(before[0]):
            record(conn, admin.id, "user.roles", user_id, before=sorted(before[0]), after=updates["roles"])
        if "is_admin" in updates and updates["is_admin"] != before[1]:
            record(conn, admin.id, "user.admin", user_id, value=updates["is_admin"])
        if "is_active" in updates and updates["is_active"] != before[2]:
            record(conn, admin.id, "user.active", user_id, value=updates["is_active"])
    return _user_out(row)


REQUEST_SQL = """
SELECT r.id::text, u.id::text, u.name, u.email, u.team, u.roles, r.role, r.reason, r.status, r.note,
       d.name, r.decided_at, r.created_at
FROM access_requests r
JOIN users u ON u.id = r.user_id
LEFT JOIN users d ON d.id = r.decided_by
"""


def _request_out(row) -> AccessRequestOut:
    return AccessRequestOut(**dict(zip(AccessRequestOut.model_fields, row)))


@router.get("/requests", response_model=list[AccessRequestOut])
def list_requests(
    which: Literal["pending", "decided"] = Query("pending", alias="status"),
    _: User = Depends(admin_user),
) -> list[AccessRequestOut]:
    where = "r.status = 'pending' ORDER BY r.created_at" if which == "pending" else \
        "r.status <> 'pending' ORDER BY coalesce(r.decided_at, r.created_at) DESC LIMIT 100"
    with connect() as conn:
        rows = conn.execute(f"{REQUEST_SQL} WHERE {where}").fetchall()
    return [_request_out(row) for row in rows]


@router.post("/requests/{request_id}/decision", response_model=AccessRequestOut)
def decide(request_id: UUID, body: Decision, admin: User = Depends(admin_user)) -> AccessRequestOut:
    with connect() as conn:
        found = conn.execute(
            "SELECT user_id::text, role FROM access_requests WHERE id = %s AND status = 'pending' FOR UPDATE",
            (str(request_id),),
        ).fetchone()
        if not found:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "This request was already handled or doesn't exist")
        user_id, role = found
        conn.execute(
            "UPDATE access_requests SET status = %s, note = %s, decided_by = %s, decided_at = now() WHERE id = %s",
            ("approved" if body.approve else "denied", body.note, admin.id, str(request_id)),
        )
        if body.approve:
            conn.execute(
                "UPDATE users SET roles = (SELECT array_agg(DISTINCT r ORDER BY r) FROM unnest(roles || %s::text) r) "
                "WHERE id = %s",
                (role, user_id),
            )
        record(conn, admin.id, "request.approved" if body.approve else "request.denied", user_id,
               role=role, note=body.note)
        row = conn.execute(f"{REQUEST_SQL} WHERE r.id = %s", (str(request_id),)).fetchone()
    return _request_out(row)


@router.get("/activity", response_model=list[ActivityOut])
def activity(limit: int = Query(100, ge=1, le=500), _: User = Depends(admin_user)) -> list[ActivityOut]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT a.id, actor.name, a.action, target.name, a.details, a.created_at FROM audit_log a "
            "LEFT JOIN users actor ON actor.id = a.actor_id LEFT JOIN users target ON target.id = a.target_id "
            "ORDER BY a.created_at DESC LIMIT %s",
            (limit,),
        ).fetchall()
    return [ActivityOut(**dict(zip(ActivityOut.model_fields, row))) for row in rows]
