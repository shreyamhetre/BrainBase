"""Activity log: one row per change, shown in the admin console."""

import json

import psycopg


def record(conn: psycopg.Connection, actor_id: str | None, action: str,
           target_id: str | None = None, **details) -> None:
    """Write inside the caller's transaction, so the log and the change commit together."""
    conn.execute(
        "INSERT INTO audit_log (actor_id, action, target_id, details) VALUES (%s, %s, %s, %s)",
        (actor_id, action, target_id, json.dumps(details)),
    )
