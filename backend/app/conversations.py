"""Saved chats: create, append, read history for follow-ups."""

import json

import psycopg

HISTORY_MESSAGES = 6     # how many earlier messages the router sees for follow-ups
HISTORY_CHARS = 600      # per message, so long answers don't crowd the router


def title_from(message: str) -> str:
    first = " ".join(message.split())
    return first if len(first) <= 60 else first[:57].rstrip() + "…"


def get_or_create(conn: psycopg.Connection, user_id: str, conversation_id: str | None, message: str) -> str:
    """The person's conversation, or a new one when none is given (or it isn't theirs)."""
    if conversation_id:
        row = conn.execute("SELECT id::text FROM conversations WHERE id::text = %s AND user_id = %s",
                           (conversation_id, user_id)).fetchone()
        if row:
            return row[0]
    return conn.execute("INSERT INTO conversations (user_id, title) VALUES (%s, %s) RETURNING id::text",
                        (user_id, title_from(message))).fetchone()[0]


def history(conn: psycopg.Connection, conversation_id: str) -> list[dict]:
    """The last few messages, oldest first, as {role, content}."""
    rows = conn.execute(
        "SELECT role, content FROM (SELECT id, role, content FROM messages WHERE conversation_id = %s "
        "ORDER BY id DESC LIMIT %s) recent ORDER BY id",
        (conversation_id, HISTORY_MESSAGES),
    ).fetchall()
    return [{"role": role, "content": content[:HISTORY_CHARS]} for role, content in rows]


def save_turn(conn: psycopg.Connection, conversation_id: str, message: str, kind: str, text: str, payload: dict) -> None:
    conn.execute("INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'user', %s)", (conversation_id, message))
    conn.execute("INSERT INTO messages (conversation_id, role, content, kind, payload) VALUES (%s, 'assistant', %s, %s, %s)",
                 (conversation_id, text, kind, json.dumps(payload)))
    conn.execute("UPDATE conversations SET updated_at = now() WHERE id = %s", (conversation_id,))
