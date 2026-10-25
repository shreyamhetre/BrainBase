"""The Knowledge library: what GitMore knows, and documents people add.

- Everyone sees the sources and documents they can read.
- People whose role may add documents (and admins) upload a PDF or Word file, choosing who can
  read it (their own roles or everyone), or link a file in the connected GitLab group (its
  access comes from the project and can't be widened).
- The person who added a document, or an admin, can replace, refresh or remove it.
- Original files open only for people who can read the document.
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from app.audit import record
from app.auth import User, current_user, search_roles
from app.db.connection import connect
from app.knowledge import (KnowledgeError, can_add, fetch_gitlab_file, new_upload_id, parse, parse_gitlab_link,
                           shareable_roles, store, title_from)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

SOURCE_NAMES = {"handbook": "GitLab handbook", "slack": "Slack threads", "gitlab_issue": "GitLab issues",
                "gitlab_wiki": "GitLab wiki pages"}


class SourceSummary(BaseModel):
    source: str
    name: str
    documents: int
    last_updated: datetime | None


class LibraryDocument(BaseModel):
    id: int
    title: str
    kind: str                 # pdf, word, gitlab_file
    url: str
    file_name: str | None
    added_by: str | None
    added_at: datetime
    allowed_roles: list[str]
    chunks: int
    can_manage: bool


class Library(BaseModel):
    can_add: bool
    shareable_roles: list[str]
    sources: list[SourceSummary]
    documents: list[LibraryDocument]


class LinkIn(BaseModel):
    url: str = Field(min_length=10, max_length=600)
    title: str | None = Field(default=None, max_length=200)


DOC_SQL = """
SELECT d.id, d.title, coalesce(d.metadata->>'kind', 'document'), d.url, f.file_name, u.name, d.synced_at,
       d.allowed_roles, (SELECT count(*) FROM chunks c WHERE c.document_id = d.id), d.added_by::text
FROM documents d LEFT JOIN users u ON u.id = d.added_by LEFT JOIN document_files f ON f.document_id = d.id
WHERE d.added_by IS NOT NULL AND (%(admin)s OR d.allowed_roles && %(roles)s)
"""


def _doc(row, user: User) -> LibraryDocument:
    did, title, kind, url, file_name, added_by, added_at, roles, chunks, owner = row
    return LibraryDocument(id=did, title=title, kind=kind, url=url, file_name=file_name, added_by=added_by,
                           added_at=added_at, allowed_roles=roles, chunks=chunks,
                           can_manage=user.is_admin or owner == user.id)


def _readable(user: User) -> dict:
    return {"admin": user.is_admin, "roles": [*search_roles(user), "all"]}


def _get(conn, doc_id: int, user: User) -> LibraryDocument:
    row = conn.execute(f"{DOC_SQL} AND d.id = %(id)s", {**_readable(user), "id": doc_id}).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such document")
    return _doc(row, user)


def _roles_for_upload(user: User, allowed_roles: str) -> list[str]:
    wanted = sorted({r.strip() for r in allowed_roles.split(",") if r.strip()})
    if not wanted:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose who can read this document")
    if not user.is_admin and set(wanted) - set(shareable_roles(user)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can share only with everyone or with roles you have")
    return ["all"] if "all" in wanted else wanted


@router.get("", response_model=Library)
def library(user: User = Depends(current_user)) -> Library:
    readable = _readable(user)
    with connect() as conn:
        sources = conn.execute(
            "SELECT source, count(*), max(updated_at) FROM documents "
            "WHERE added_by IS NULL AND (%(admin)s OR allowed_roles && %(roles)s) GROUP BY source ORDER BY count(*) DESC",
            readable,
        ).fetchall()
        docs = conn.execute(f"{DOC_SQL} ORDER BY d.synced_at DESC", readable).fetchall()
        allowed = can_add(conn, user)
    roles = shareable_roles(user) if not user.is_admin else ["all", *user.roles]
    return Library(can_add=allowed, shareable_roles=roles,
                   sources=[SourceSummary(source=s, name=SOURCE_NAMES.get(s, s), documents=n, last_updated=u)
                            for s, n, u in sources],
                   documents=[_doc(r, user) for r in docs])


def _require_can_add(conn, user: User) -> None:
    if not can_add(conn, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role can't add documents. Ask an admin.")


@router.post("/upload", response_model=LibraryDocument, status_code=status.HTTP_201_CREATED)
def upload(file: UploadFile = File(...), allowed_roles: str = Form(...), title: str = Form(""),
           user: User = Depends(current_user)) -> LibraryDocument:
    """A plain def: parsing and embedding run in a worker thread, not on the server's event loop."""
    data = file.file.read()
    roles = _roles_for_upload(user, allowed_roles)
    try:
        text, kind = parse(file.filename or "file", file.content_type or "", data)
    except KnowledgeError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    external_id = new_upload_id()
    name = title.strip() or title_from(file.filename or "", text)
    with connect() as conn:
        _require_can_add(conn, user)
        try:
            doc_id = store(conn, source="upload", external_id=external_id, title=name,
                           url=f"/api/knowledge/files/{external_id}", text=text, allowed_roles=roles, user=user,
                           metadata={"kind": "pdf" if kind.endswith("pdf") else "word" if "word" in kind else "text",
                                     "file_name": file.filename})
        except KnowledgeError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
        conn.execute("INSERT INTO document_files (document_id, file_name, content_type, size_bytes, data) "
                     "VALUES (%s, %s, %s, %s, %s)", (doc_id, file.filename or "file", kind, len(data), data))
        record(conn, user.id, "knowledge.added", title=name, kind="upload", roles=roles)
        return _get(conn, doc_id, user)


@router.post("/link", response_model=LibraryDocument, status_code=status.HTTP_201_CREATED)
def add_link(body: LinkIn, user: User = Depends(current_user)) -> LibraryDocument:
    with connect() as conn:
        _require_can_add(conn, user)
        group = conn.execute("SELECT config->>'group' FROM connectors WHERE kind = 'gitlab' AND enabled "
                             "ORDER BY created_at LIMIT 1").fetchone()
        if not group:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Connect GitLab on the Connectors page first.")
        try:
            link = parse_gitlab_link(body.url, group[0])
            data, project = fetch_gitlab_file(conn, link)
            # The file belongs to its project: you must be able to read it, and it keeps the project's access
            if not user.is_admin and not set(project["allowed_roles"]) & {*user.roles, "all"}:
                raise KnowledgeError(f"You can't read the {project['project']} project, so you can't add its files.")
            text, kind = parse(link.file_path, "", data)
            name = (body.title or "").strip() or title_from(link.file_path.rsplit("/", 1)[-1], text)
            doc_id = store(conn, source="gitlab_file", external_id=f"{link.project_path}:{link.ref}:{link.file_path}",
                           title=name, url=body.url.strip(), text=text, allowed_roles=project["allowed_roles"], user=user,
                           metadata={"kind": "gitlab_file", "project": link.project_path, "ref": link.ref,
                                     "path": link.file_path}, access_id=project["access_id"], section=link.project_path)
        except KnowledgeError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
        record(conn, user.id, "knowledge.added", title=name, kind="gitlab_file", roles=project["allowed_roles"])
        return _get(conn, doc_id, user)


def _manage(conn, doc_id: int, user: User):
    row = conn.execute("SELECT source, external_id, title, url, allowed_roles, metadata, added_by::text FROM documents "
                       "WHERE id = %s AND added_by IS NOT NULL", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such document")
    if not user.is_admin and row[6] != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the person who added it, or an admin, can change it")
    return row


@router.post("/{doc_id}/refresh", response_model=LibraryDocument)
def refresh_link(doc_id: int, user: User = Depends(current_user)) -> LibraryDocument:
    """Fetch a linked GitLab file again; only changed text is re-embedded."""
    with connect() as conn:
        source, external_id, title, url, roles, metadata, _ = _manage(conn, doc_id, user)
        if source != "gitlab_file":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only GitLab links can be refreshed; replace a file instead")
        try:
            group = conn.execute("SELECT config->>'group' FROM connectors WHERE kind = 'gitlab' ORDER BY created_at LIMIT 1").fetchone()[0]
            link = parse_gitlab_link(url, group)
            data, project = fetch_gitlab_file(conn, link)
            text, _ = parse(link.file_path, "", data)
            store(conn, source=source, external_id=external_id, title=title, url=url, text=text,
                  allowed_roles=project["allowed_roles"], user=user, metadata=metadata, access_id=project["access_id"],
                  section=link.project_path)
        except KnowledgeError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
        record(conn, user.id, "knowledge.refreshed", title=title)
        return _get(conn, doc_id, user)


@router.put("/{doc_id}/file", response_model=LibraryDocument)
def replace_file(doc_id: int, file: UploadFile = File(...), user: User = Depends(current_user)) -> LibraryDocument:
    data = file.file.read()
    with connect() as conn:
        source, external_id, title, url, roles, metadata, _ = _manage(conn, doc_id, user)
        if source != "upload":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only uploaded files can be replaced; refresh a link instead")
        try:
            text, kind = parse(file.filename or "file", file.content_type or "", data)
            store(conn, source=source, external_id=external_id, title=title, url=url, text=text, allowed_roles=roles,
                  user=user, metadata={**metadata, "file_name": file.filename})
        except KnowledgeError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
        conn.execute("UPDATE document_files SET file_name = %s, content_type = %s, size_bytes = %s, data = %s "
                     "WHERE document_id = %s", (file.filename or "file", kind, len(data), data, doc_id))
        record(conn, user.id, "knowledge.replaced", title=title)
        return _get(conn, doc_id, user)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(doc_id: int, user: User = Depends(current_user)) -> None:
    with connect() as conn:
        _, _, title, *_ = _manage(conn, doc_id, user)
        conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))  # chunks and the file go with it
        record(conn, user.id, "knowledge.removed", title=title)


@router.get("/files/{external_id}")
def open_file(external_id: str, user: User = Depends(current_user)) -> Response:
    """The original uploaded file, for people who can read the document (citations link here)."""
    with connect() as conn:
        row = conn.execute(
            "SELECT f.file_name, f.content_type, f.data FROM documents d JOIN document_files f ON f.document_id = d.id "
            "WHERE d.source = 'upload' AND d.external_id = %(eid)s AND (%(admin)s OR d.allowed_roles && %(roles)s)",
            {**_readable(user), "eid": external_id},
        ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such file, or you can't read it")
    name, content_type, data = row
    return Response(bytes(data), media_type=content_type,
                    headers={"Content-Disposition": f"inline; filename*=UTF-8''{json.dumps(name)[1:-1]}"})
