"""Add the demo Slack and GitLab connectors from .env, and map their channels and projects to roles.

The tokens are encrypted into the database (the same as adding them in the app), and the
role mapping comes from data/synthetic: channels.*.allowed_roles in slack.json and
project_access in gitlab_issues.json. Anything not listed there stays admin-only.

Safe to re-run: an existing connector of the same kind is refreshed, not duplicated.

Usage: python backend/scripts/seed_connectors.py
"""

import json
import os

from psycopg.types.json import Jsonb

from app.api.settings_routes import _discover
from app.audit import record
from app.config import DATA_DIR
from app.connectors.clients import client
from app.db.connection import connect
from app.vault import encrypt

SYNTHETIC = DATA_DIR / "synthetic"


def mapping() -> dict[str, dict[str, list[str]]]:
    slack = json.loads((SYNTHETIC / "slack.json").read_text(encoding="utf-8"))["channels"]
    gitlab = json.loads((SYNTHETIC / "gitlab_issues.json").read_text(encoding="utf-8"))["project_access"]
    return {
        "slack": {f"#{name}": c["allowed_roles"] for name, c in slack.items()},
        "gitlab": dict(gitlab),
    }


def seed(conn, kind: str, name: str, token: str, config: dict, roles_by_name: dict[str, list[str]]) -> None:
    api = client(kind, token, config)
    config = config | api.check()
    row = conn.execute("SELECT id::text FROM connectors WHERE kind = %s ORDER BY created_at LIMIT 1", (kind,)).fetchone()
    if row:
        connector_id = row[0]
        conn.execute("UPDATE connectors SET config = %s, token_encrypted = %s, status = 'connected', last_error = NULL, "
                     "last_checked_at = now() WHERE id = %s", (Jsonb(config), encrypt(token), connector_id))
    else:
        connector_id = conn.execute(
            "INSERT INTO connectors (kind, name, config, token_encrypted, last_checked_at) "
            "VALUES (%s, %s, %s, %s, now()) RETURNING id::text",
            (kind, name, Jsonb(config), encrypt(token)),
        ).fetchone()[0]
        record(conn, None, "connector.added", name=name, kind=kind)

    found = _discover(conn, connector_id, kind, token, config)
    mapped = 0
    for container, roles in roles_by_name.items():
        mapped += conn.execute(
            "UPDATE source_access SET allowed_roles = %s, updated_at = now() "
            "WHERE connector_id = %s AND container_name = %s AND allowed_roles = '{}'",
            (sorted(roles), connector_id, container),
        ).rowcount
    unmapped = conn.execute("SELECT array_agg(container_name) FROM source_access "
                            "WHERE connector_id = %s AND allowed_roles = '{}'", (connector_id,)).fetchone()[0]
    print(f"{name}: {found} found, {mapped} newly mapped; admin-only until mapped: {unmapped or 'none'}")


def main() -> None:
    roles = mapping()
    with connect() as conn:
        seed(conn, "slack", "GitMore Demo Slack", os.environ["SLACK_BOT_TOKEN"], {}, roles["slack"])
        seed(conn, "gitlab", "GitMore Demo GitLab", os.environ["GITLAB_TOKEN"],
             {"url": os.environ["GITLAB_URL"], "group": os.environ["GITLAB_GROUP"]}, roles["gitlab"])


if __name__ == "__main__":
    main()
