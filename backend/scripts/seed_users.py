"""Create the admin and the 20 demo people in the users table. Safe to re-run: existing
users get their name, roles and team refreshed, but their password is left unchanged.

Passwords come from .env: ADMIN_EMAIL / ADMIN_PASSWORD for the admin, and
DEMO_USER_PASSWORD for every demo person.

Usage: python backend/scripts/seed_users.py
"""

import json
import os

from app.auth import hash_password
from app.config import DATA_DIR
from app.db.connection import connect
from app.roles import content_roles

PEOPLE_FILE = DATA_DIR / "synthetic" / "people.json"

UPSERT = """
INSERT INTO users (email, name, password_hash, roles, is_admin, team, title, slack_handle, gitlab_username)
VALUES (%(email)s, %(name)s, %(password_hash)s, %(roles)s, %(is_admin)s, %(team)s, %(title)s,
        %(handle)s, %(handle)s)
ON CONFLICT (email) DO UPDATE SET
    name = EXCLUDED.name, roles = EXCLUDED.roles, is_admin = EXCLUDED.is_admin, team = EXCLUDED.team,
    title = EXCLUDED.title, slack_handle = EXCLUDED.slack_handle, gitlab_username = EXCLUDED.gitlab_username
RETURNING (xmax = 0) AS inserted
"""


def main() -> None:
    admin_email, admin_password = os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"]
    demo_password = os.environ["DEMO_USER_PASSWORD"]
    people = json.loads(PEOPLE_FILE.read_text(encoding="utf-8"))["people"]

    admin = {"email": admin_email.lower(), "name": "GitMore Admin", "roles": [], "is_admin": True,
             "team": "Admin", "title": "Administrator", "handle": None,
             "password_hash": hash_password(admin_password)}
    demo_hash = hash_password(demo_password)  # bcrypt is slow on purpose; hash once for all 20
    rows = [admin] + [{**p, "is_admin": False, "password_hash": demo_hash} for p in people]

    created = 0
    with connect() as conn:
        admin["roles"] = content_roles(conn)
        for row in rows:
            created += conn.execute(UPSERT, row).fetchone()[0]
        total = conn.execute("SELECT count(*) FROM users").fetchone()[0]
    print(f"Seeded {len(rows)} users ({created} new, {len(rows) - created} updated); {total} in the table")


if __name__ == "__main__":
    main()
