"""The logged-in person's own chats: list, open, delete. Nobody else's, admins included."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth import User, current_user
from app.db.connection import connect

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationOut(BaseModel):
    id: str
    title: str
    updated_at: datetime


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    kind: str | None
    payload: dict
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


@router.get("", response_model=list[ConversationOut])
def list_conversations(limit: int = Query(30, ge=1, le=100), user: User = Depends(current_user)) -> list[ConversationOut]:
    with connect() as conn:
        rows = conn.execute("SELECT id::text, title, updated_at FROM conversations WHERE user_id = %s "
                            "ORDER BY updated_at DESC LIMIT %s", (user.id, limit)).fetchall()
    return [ConversationOut(id=i, title=t, updated_at=u) for i, t, u in rows]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def open_conversation(conversation_id: UUID, user: User = Depends(current_user)) -> ConversationDetail:
    with connect() as conn:
        row = conn.execute("SELECT id::text, title, updated_at FROM conversations WHERE id = %s AND user_id = %s",
                           (str(conversation_id), user.id)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such chat")
        messages = conn.execute("SELECT id, role, content, kind, payload, created_at FROM messages "
                                "WHERE conversation_id = %s ORDER BY id", (row[0],)).fetchall()
        # Actions may have been confirmed since: show their current state, not the one at proposal time
        action_ids = [m[4]["action"]["id"] for m in messages if m[3] in ("action", "choose") and m[4].get("action")]
        current = {a[0]: a for a in conn.execute(
            "SELECT id::text, status, arguments, result_url FROM actions WHERE id::text = ANY(%s) AND user_id = %s",
            (action_ids, user.id))} if action_ids else {}
    out = []
    for mid, role, content, kind, payload, created in messages:
        action = payload.get("action")
        if action and action["id"] in current:
            _, st, args, url = current[action["id"]]
            payload = {**payload, "action": {**action, "status": st, "arguments": args, "result_url": url}}
        out.append(MessageOut(id=mid, role=role, content=content, kind=kind, payload=payload, created_at=created))
    return ConversationDetail(id=row[0], title=row[1], updated_at=row[2], messages=out)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: UUID, user: User = Depends(current_user)) -> None:
    with connect() as conn:
        if not conn.execute("DELETE FROM conversations WHERE id = %s AND user_id = %s RETURNING id",
                            (str(conversation_id), user.id)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No such chat")
