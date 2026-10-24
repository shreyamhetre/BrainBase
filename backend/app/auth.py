"""Login: password hashing, JWT tokens and the FastAPI dependencies that protect routes.

The JWT only proves who you are (user id + expiry). Roles are read from the database on
every request, so a role change by the admin takes effect immediately, not after the
token expires.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status

from app.config import CONTENT_ROLES, JWT_EXPIRE_HOURS, JWT_SECRET
from app.db.connection import connect

ALGORITHM = "HS256"
COOKIE_NAME = "gitmore_token"


@dataclass
class User:
    id: str
    email: str
    name: str
    roles: list[str]
    is_admin: bool
    team: str | None
    title: str | None


USER_COLUMNS = "id::text, email, name, roles, is_admin, team, title"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(user_id: str) -> str:
    if len(JWT_SECRET) < 32:  # a short or placeholder secret lets anyone forge login tokens
        raise RuntimeError("JWT_SECRET in .env must be a random string of at least 32 characters")
    now = datetime.now(timezone.utc)
    claims = {"sub": user_id, "iat": now, "exp": now + timedelta(hours=JWT_EXPIRE_HOURS)}
    return jwt.encode(claims, JWT_SECRET, algorithm=ALGORITHM)


def get_user(user_id: str) -> User | None:
    with connect() as conn:
        row = conn.execute(
            f"SELECT {USER_COLUMNS} FROM users WHERE id = %s AND is_active", (user_id,)
        ).fetchone()
    if not row:
        return None
    user = User(*row)
    if user.is_admin:
        user.roles = list(CONTENT_ROLES)  # admins can read everything, including roles added later
    return user


def _token_from(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:]
    return request.cookies.get(COOKIE_NAME)  # the web UI sends an httpOnly cookie


def current_user(request: Request) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in or session expired")
    token = _token_from(request)
    if not token:
        raise unauthorized
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise unauthorized from None
    user = get_user(claims["sub"])
    if not user:
        raise unauthorized
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user
