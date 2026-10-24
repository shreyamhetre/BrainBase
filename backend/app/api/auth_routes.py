"""Sign-up, login, logout and the current user.

New accounts get no content roles: they can read everything marked 'all' (the handbook).
Only an admin can grant roles, in the admin console.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, EmailStr, Field

from app.auth import (COOKIE_NAME, USER_COLUMNS, User, _token_from, close_session, create_token,
                      current_user, hash_password, session_from, verify_password)
from app.config import ALLOWED_EMAIL_DOMAIN, JWT_EXPIRE_HOURS
from app.db.connection import connect

router = APIRouter(prefix="/auth", tags=["auth"])


def require_company_email(email: str) -> str:
    """Only company addresses (e.g. name@gitmore.com) can sign up or log in."""
    email = email.lower()
    if email.rsplit("@", 1)[-1] != ALLOWED_EMAIL_DOMAIN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Use your @{ALLOWED_EMAIL_DOMAIN} email")
    return email


class SignupRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    roles: list[str]
    is_admin: bool
    team: str | None
    title: str | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _issue(request: Request, response: Response, user: User) -> TokenOut:
    token = create_token(user.id, request.headers.get("user-agent"))
    # httpOnly: page scripts can't read the token, which protects it from XSS.
    # secure: sent over HTTPS only, whenever the site is served over HTTPS.
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=request.url.scheme == "https",
                        max_age=JWT_EXPIRE_HOURS * 3600, path="/")
    return TokenOut(access_token=token, user=UserOut(**user.__dict__))


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, request: Request, response: Response) -> TokenOut:
    email = require_company_email(body.email)
    try:
        with connect() as conn:
            row = conn.execute(
                f"INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s) "
                f"RETURNING {USER_COLUMNS}",
                (email, body.name.strip(), hash_password(body.password)),
            ).fetchone()
    except UniqueViolation:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists") from None
    return _issue(request, response, User(*row))


@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest, request: Request, response: Response) -> TokenOut:
    email = require_company_email(body.email)
    with connect() as conn:
        row = conn.execute(
            f"SELECT {USER_COLUMNS}, password_hash FROM users WHERE lower(email) = %s AND is_active",
            (email,),
        ).fetchone()
        # Same message for unknown email and wrong password, so emails can't be probed
        if not row or not verify_password(body.password, row[-1]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
        conn.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (row[0],))
    return _issue(request, response, User(*row[:-1]))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> None:
    """Close the session on the server, so this token stops working even if it was copied, and clear the cookie."""
    token = _token_from(request)
    session_id = session_from(token) if token else None
    if session_id:
        close_session(session_id)
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut(**user.__dict__)
