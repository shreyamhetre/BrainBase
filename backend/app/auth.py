"""Login: password hashing, JWT tokens, server-side sessions and the dependencies that protect routes.

The JWT carries the user id, an expiry and a session id (jti). Every request checks that
session is still open, so logging out or changing a password makes old tokens useless at
once. Roles are read from the database on every request, so a role change by the admin
takes effect immediately.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status

from app.config import JWT_EXPIRE_HOURS, JWT_SECRET
from app.db.connection import connect
from app.ingestion.store import ADMINS_ONLY
from app.roles import content_roles

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


def create_token(user_id: str, user_agent: str | None = None) -> str:
    """Open a session and return a JWT that points at it."""
    if len(JWT_SECRET) < 32:  # a short or placeholder secret lets anyone forge login tokens
        raise RuntimeError("JWT_SECRET in .env must be a random string of at least 32 characters")
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=JWT_EXPIRE_HOURS)
    with connect() as conn:
        session_id = conn.execute(
            "INSERT INTO sessions (user_id, expires_at, user_agent) VALUES (%s, %s, %s) RETURNING id::text",
            (user_id, expires, (user_agent or "")[:300]),
        ).fetchone()[0]
    claims = {"sub": user_id, "jti": session_id, "iat": now, "exp": expires}
    return jwt.encode(claims, JWT_SECRET, algorithm=ALGORITHM)


def close_session(session_id: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE sessions SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL", (session_id,))


def close_user_sessions(user_id: str, keep: str | None = None) -> int:
    """Log a user out everywhere, optionally keeping the current session."""
    with connect() as conn:
        return conn.execute(
            "UPDATE sessions SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL AND id::text <> %s",
            (user_id, keep or ""),
        ).rowcount


def session_from(token: str) -> str | None:
    """The session id inside a valid token, or None."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM]).get("jti")
    except jwt.PyJWTError:
        return None


def get_user(user_id: str) -> User | None:
    with connect() as conn:
        row = conn.execute(
            f"SELECT {USER_COLUMNS} FROM users WHERE id = %s AND is_active", (user_id,)
        ).fetchone()
        if not row:
            return None
        user = User(*row)
        if user.is_admin:
            user.roles = content_roles(conn)  # admins can read everything, including roles added later
    return user


def search_roles(user: User) -> list[str]:
    """Roles the search filter uses. Admins also see content nobody has been given access to yet."""
    return [*user.roles, ADMINS_ONLY] if user.is_admin else list(user.roles)


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
    with connect() as conn:
        open_session = conn.execute(
            "SELECT 1 FROM sessions WHERE id::text = %s AND user_id::text = %s AND revoked_at IS NULL AND expires_at > now()",
            (claims.get("jti") or "", claims["sub"]),
        ).fetchone()
    if not open_session:  # logged out, password changed, or a token from before sessions existed
        raise unauthorized
    user = get_user(claims["sub"])
    if not user:
        raise unauthorized
    request.state.session_id = claims["jti"]
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user
