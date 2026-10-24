"""Encrypt tool tokens before they go into the database, decrypt them only when calling the tool.

The key (SECRETS_KEY) lives in .env, not in the database, so a copy of the database alone
can't use the tokens. Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import SECRETS_KEY


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    if not SECRETS_KEY:
        raise RuntimeError("SECRETS_KEY is not set in .env; it encrypts connector tokens")
    return Fernet(SECRETS_KEY.encode())


def encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise RuntimeError("Can't decrypt a stored token: SECRETS_KEY changed since it was saved") from None


def hint(secret: str) -> str:
    """The last 4 characters, so admins can tell tokens apart without seeing them."""
    return f"…{secret[-4:]}" if len(secret) > 8 else "…"
