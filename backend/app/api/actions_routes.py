"""Confirm or cancel an action GitMore proposed in the chat.

Only the person who asked can confirm it. The checks run again at confirm time (tool still
on, role still allowed, project still theirs), the edited inputs are signed with who asked,
the MCP tool runs, and the result goes to the action row and the activity log.
"""

import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.actions import ActionRefused, check, find_created_issue, result_link, scope_for, sign
from app.audit import record
from app.auth import User, current_user
from app.db.connection import connect
from app.mcp_client import McpError, call_tool
from app.vault import decrypt

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionOut(BaseModel):
    id: str
    tool: str
    server: str
    summary: str
    arguments: dict
    status: str
    result_text: str | None
    result_url: str | None
    created_at: datetime


class Confirm(BaseModel):
    arguments: dict   # as edited on the card


COLUMNS = "id::text, tool_name, server_name, summary, arguments, status, result_text, result_url, created_at"


def _get(conn, action_id: str, user: User) -> ActionOut:
    row = conn.execute(f"SELECT {COLUMNS} FROM actions WHERE id = %s AND user_id = %s", (action_id, user.id)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such action")
    return ActionOut(**dict(zip(ActionOut.model_fields, row)))


@router.post("/{action_id}/confirm", response_model=ActionOut)
def confirm(action_id: UUID, body: Confirm, user: User = Depends(current_user)) -> ActionOut:
    aid = str(action_id)
    with connect() as conn:
        action = _get(conn, aid, user)
        if action.status != "proposed":
            raise HTTPException(status.HTTP_409_CONFLICT, f"This action is already {action.status}")
        try:
            tool = check(scope_for(conn, user), user, action.tool, dict(body.arguments))
        except ActionRefused as e:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from None
        arguments = sign(body.arguments, user)
        # Claim it first, so a double click can't run it twice
        claimed = conn.execute("UPDATE actions SET status = 'failed', decided_at = now(), arguments = %s "
                               "WHERE id = %s AND status = 'proposed' RETURNING id", (json.dumps(arguments), aid)).fetchone()
        if not claimed:
            raise HTTPException(status.HTTP_409_CONFLICT, "This action was already handled")
        conn.commit()

    try:
        result = call_tool(tool.server_url, decrypt(tool.auth_encrypted), tool.name, arguments)
        ok, text, url = result.ok, result.text, result_link(result.text, result.data)
    except (McpError, RuntimeError) as e:
        ok, text, url = False, str(e), None

    with connect() as conn:
        if not ok and tool.name == "save_work_item" and "work_item_iid" not in arguments:
            found = find_created_issue(conn, str(arguments.get("project_id", "")), str(arguments.get("title", "")),
                                       action.created_at)
            if found:  # created, but the server failed reading it back: report the truth
                ok, url, text = True, found, f"Created. GitLab reported afterwards: {text}"
        conn.execute("UPDATE actions SET status = %s, result_text = %s, result_url = %s WHERE id = %s",
                     ("done" if ok else "failed", (text or "")[:4000], url, aid))
        record(conn, user.id, "action.done" if ok else "action.failed", user.id,
               tool=f"{tool.server_name} · {tool.name}", summary=action.summary, url=url)
        return _get(conn, aid, user)


@router.post("/{action_id}/cancel", response_model=ActionOut)
def cancel(action_id: UUID, user: User = Depends(current_user)) -> ActionOut:
    aid = str(action_id)
    with connect() as conn:
        if not conn.execute("UPDATE actions SET status = 'cancelled', decided_at = now() "
                            "WHERE id = %s AND user_id = %s AND status = 'proposed' RETURNING id", (aid, user.id)).fetchone():
            raise HTTPException(status.HTTP_409_CONFLICT, "This action was already handled or doesn't exist")
        return _get(conn, aid, user)
