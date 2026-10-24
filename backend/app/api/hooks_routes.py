"""GitLab webhooks: GitLab calls this when an issue, comment or wiki page changes.

GitLab sends the secret we gave it in the X-Gitlab-Token header; anything without the
right secret is refused. The project is re-synced a few seconds later (debounced).
This route must be reachable from GitLab, so it needs a public URL (PUBLIC_URL in .env).
"""

import hmac
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.connectors.events import schedule_resync
from app.db.connection import connect
from app.vault import decrypt

router = APIRouter(prefix="/hooks", tags=["webhooks"])

WATCHED = {"issue", "note", "wiki_page"}


@router.post("/gitlab/{connector_id}", status_code=status.HTTP_202_ACCEPTED)
async def gitlab_hook(connector_id: UUID, request: Request,
                      x_gitlab_token: str = Header(default="")) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT events_secret_encrypted, enabled FROM connectors "
                           "WHERE id = %s AND kind = 'gitlab'", (str(connector_id),)).fetchone()
    if not row or not row[0] or not hmac.compare_digest(decrypt(row[0]), x_gitlab_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown connector or wrong secret")
    if not row[1]:
        return {"ignored": "connector is turned off"}

    body = await request.json()
    project_id = (body.get("project") or {}).get("id")
    if body.get("object_kind") not in WATCHED or not project_id:
        return {"ignored": body.get("object_kind")}
    schedule_resync(str(connector_id), str(project_id))
    return {"queued": body["object_kind"]}
