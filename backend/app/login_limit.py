"""Slow down password guessing: too many failed logins lock an email (or an address) for a while.

Counts live in the database, so they survive restarts and are shared by every API worker.
"""

from fastapi import HTTPException, Request, status

from app.db.connection import connect

WINDOW_MINUTES = 15
MAX_PER_EMAIL = 5     # wrong passwords for one account
MAX_PER_IP = 20       # failures from one address, across accounts


def client_ip(request: Request) -> str:
    """The browser's address. The Next.js proxy runs on this machine and passes it on in X-Forwarded-For."""
    direct = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and direct in ("127.0.0.1", "::1", "localhost"):
        return forwarded.split(",")[0].strip()
    return direct


def check(email: str, ip: str) -> None:
    """Refuse the attempt before checking the password when the limit is reached."""
    with connect() as conn:
        by_email, by_ip, oldest = conn.execute(
            "SELECT count(*) FILTER (WHERE email = %(email)s), count(*) FILTER (WHERE ip = %(ip)s), "
            "min(at) FILTER (WHERE email = %(email)s OR ip = %(ip)s) "
            "FROM login_failures WHERE at > now() - make_interval(mins => %(window)s)",
            {"email": email, "ip": ip, "window": WINDOW_MINUTES},
        ).fetchone()
        wait = conn.execute("SELECT ceil(extract(epoch FROM %s + make_interval(mins => %s) - now()) / 60)",
                            (oldest, WINDOW_MINUTES)).fetchone()[0] if oldest else WINDOW_MINUTES
    if by_email >= MAX_PER_EMAIL or by_ip >= MAX_PER_IP:
        minutes = max(1, int(wait or 1))
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
                            headers={"Retry-After": str(minutes * 60)})


def failed(email: str, ip: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO login_failures (email, ip) VALUES (%s, %s)", (email, ip))
        conn.execute("DELETE FROM login_failures WHERE at < now() - interval '1 day'")


def succeeded(email: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM login_failures WHERE email = %s", (email,))
