"""The logged-in user's own account: profile, password and access requests.

Email is the login and stays a company address, so only an admin changes it.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, Field

from app.api.auth_routes import UserOut
from app.audit import record
from app.auth import User, current_user, get_user, hash_password, verify_password
from app.config import CONTENT_ROLES
from app.db.connection import connect

router = APIRouter(prefix="/account", tags=["account"])


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    title: str | None = Field(default=None, max_length=100)
    team: str | None = Field(default=None, max_length=100)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class NewRequest(BaseModel):
    role: str
    reason: str = Field(min_length=5, max_length=500)


class MyRequest(BaseModel):
    id: str
    role: str
    reason: str
    status: str
    note: str | None
    decided_at: datetime | None
    created_at: datetime


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


@router.patch("/profile", response_model=UserOut)
def update_profile(body: ProfileUpdate, user: User = Depends(current_user)) -> UserOut:
    with connect() as conn:
        conn.execute(
            "UPDATE users SET name = %s, title = %s, team = %s WHERE id = %s",
            (body.name.strip(), _clean(body.title), _clean(body.team), user.id),
        )
        record(conn, user.id, "profile.updated", user.id)
    return UserOut(**get_user(user.id).__dict__)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, user: User = Depends(current_user)) -> None:
    with connect() as conn:
        current_hash = conn.execute("SELECT password_hash FROM users WHERE id = %s", (user.id,)).fetchone()[0]
        if not verify_password(body.current_password, current_hash):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your current password is wrong")
        conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(body.new_password), user.id))
        record(conn, user.id, "password.changed", user.id)


MY_REQUEST_COLUMNS = "id::text, role, reason, status, note, decided_at, created_at"


@router.get("/requests", response_model=list[MyRequest])
def my_requests(user: User = Depends(current_user)) -> list[MyRequest]:
    with connect() as conn:
        rows = conn.execute(
            f"SELECT {MY_REQUEST_COLUMNS} FROM access_requests WHERE user_id = %s ORDER BY created_at DESC",
            (user.id,),
        ).fetchall()
    return [MyRequest(**dict(zip(MyRequest.model_fields, row))) for row in rows]


@router.post("/requests", response_model=MyRequest, status_code=status.HTTP_201_CREATED)
def request_access(body: NewRequest, user: User = Depends(current_user)) -> MyRequest:
    if body.role not in CONTENT_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown role: {body.role}")
    if body.role in user.roles:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"You already have the {body.role} role")
    try:
        with connect() as conn:
            row = conn.execute(
                f"INSERT INTO access_requests (user_id, role, reason) VALUES (%s, %s, %s) RETURNING {MY_REQUEST_COLUMNS}",
                (user.id, body.role, body.reason.strip()),
            ).fetchone()
            record(conn, user.id, "request.created", user.id, role=body.role)
    except UniqueViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, f"You already asked for {body.role}; wait for the admin") from None
    return MyRequest(**dict(zip(MyRequest.model_fields, row)))


@router.delete("/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_request(request_id: UUID, user: User = Depends(current_user)) -> None:
    with connect() as conn:
        done = conn.execute(
            "UPDATE access_requests SET status = 'cancelled', decided_at = now() "
            "WHERE id = %s AND user_id = %s AND status = 'pending' RETURNING role",
            (str(request_id), user.id),
        ).fetchone()
        if not done:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No open request to cancel")
        record(conn, user.id, "request.cancelled", user.id, role=done[0])
