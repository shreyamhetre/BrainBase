"""Admin console endpoints: list users, assign roles, make admins, deactivate accounts."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import User, admin_user
from app.config import CONTENT_ROLES
from app.db.connection import connect

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    id: str
    email: str
    name: str
    roles: list[str]
    is_admin: bool
    is_active: bool
    team: str | None
    title: str | None
    last_login_at: str | None


class UserUpdate(BaseModel):
    roles: list[str] | None = None
    is_admin: bool | None = None
    is_active: bool | None = None


@router.get("/roles")
def roles(_: User = Depends(admin_user)) -> list[str]:
    return list(CONTENT_ROLES)


@router.get("/users", response_model=list[AdminUserOut])
def list_users(_: User = Depends(admin_user)) -> list[AdminUserOut]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id::text, email, name, roles, is_admin, is_active, team, title, "
            "to_char(last_login_at, 'YYYY-MM-DD HH24:MI') FROM users ORDER BY is_admin DESC, name"
        ).fetchall()
    return [AdminUserOut(**dict(zip(AdminUserOut.model_fields, row))) for row in rows]


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
        row = conn.execute(
            f"UPDATE users SET {assignments} WHERE id = %(id)s RETURNING id::text, email, name, roles, "
            "is_admin, is_active, team, title, to_char(last_login_at, 'YYYY-MM-DD HH24:MI')",
            {**updates, "id": user_id},
        ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return AdminUserOut(**dict(zip(AdminUserOut.model_fields, row)))
