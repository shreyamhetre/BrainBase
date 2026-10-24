"""Write documents and their chunks to Postgres: one shared path for every source.

A source hands over SourceDocs. sync_documents() skips the ones whose content hash hasn't
changed, chunks and embeds the rest in GPU-sized batches, upserts them, and (on a full run)
deletes documents that are gone from the source. allowed_roles is copied onto every chunk,
so the search filter needs no join.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime

import psycopg

from app.embedding import embed
from app.ingestion.chunker import CHUNKER_VERSION, Chunk, chunk_markdown

GROUP_CHUNKS = 256     # embed this many chunks per GPU round
ADMINS_ONLY = "admins"  # pseudo-role on content nobody has been given access to yet


@dataclass
class SourceDoc:
    source: str                 # handbook, slack, gitlab_issue, gitlab_wiki
    external_id: str            # stable id in the source
    title: str
    url: str
    body: str                   # Markdown
    allowed_roles: list[str]
    updated_at: datetime | None = None
    section: str | None = None  # channel or project
    doc_type: str | None = None
    status: str | None = None
    owners: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    access_id: str | None = None
    chunks: list[Chunk] | None = None  # set to skip chunk_markdown (the handbook chunks itself)

    def __post_init__(self):
        self.allowed_roles = sorted(set(self.allowed_roles)) or [ADMINS_ONLY]

    @property
    def content_hash(self) -> str:
        # Roles are left out on purpose: an access change updates chunks directly, without re-embedding
        parts = [CHUNKER_VERSION, self.title, self.url, self.status or "",
                 self.updated_at.isoformat() if self.updated_at else "", self.body]
        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()

    def make_chunks(self) -> list[Chunk]:
        chunks = self.chunks if self.chunks is not None else chunk_markdown(self.body, self.title)
        for c in chunks:
            c.people = sorted(set(c.people) | set(self.people))
        return chunks


@dataclass
class SyncStats:
    seen: int = 0
    changed: int = 0
    unchanged: int = 0
    empty: int = 0
    deleted: int = 0
    chunks: int = 0


def write_document(conn: psycopg.Connection, doc: SourceDoc, chunks: list[Chunk], vectors) -> None:
    with conn.transaction():
        doc_id = conn.execute(
            """
            INSERT INTO documents (source, external_id, title, url, section, doc_type, status, owners,
                                   allowed_roles, updated_at, content_hash, metadata, access_id, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (source, external_id) DO UPDATE SET
                title = EXCLUDED.title, url = EXCLUDED.url, section = EXCLUDED.section,
                doc_type = EXCLUDED.doc_type, status = EXCLUDED.status, owners = EXCLUDED.owners,
                allowed_roles = EXCLUDED.allowed_roles, updated_at = EXCLUDED.updated_at,
                content_hash = EXCLUDED.content_hash, metadata = EXCLUDED.metadata,
                access_id = EXCLUDED.access_id, synced_at = now()
            RETURNING id
            """,
            (doc.source, doc.external_id, doc.title, doc.url, doc.section, doc.doc_type, doc.status, doc.owners,
             doc.allowed_roles, doc.updated_at, doc.content_hash, json.dumps(doc.metadata), doc.access_id),
        ).fetchone()[0]

        conn.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chunks (document_id, chunk_index, heading_path, anchor, content, token_count,
                                    embedding, source, section, status, allowed_roles, updated_at, people)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (doc_id, i, c.heading_path, c.anchor, c.content, c.token_count, vectors[i],
                     doc.source, doc.section, doc.status, doc.allowed_roles, doc.updated_at, c.people)
                    for i, c in enumerate(chunks)
                ],
            )


def _flush(conn: psycopg.Connection, pending: list[tuple[SourceDoc, list[Chunk]]]) -> int:
    vectors = embed([c.embed_text for _, chunks in pending for c in chunks])
    offset = 0
    for doc, chunks in pending:
        write_document(conn, doc, chunks, vectors[offset:offset + len(chunks)])
        offset += len(chunks)
    return offset


def sync_documents(conn: psycopg.Connection, docs, scope_sql: str, scope_params: tuple,
                   full: bool = True, progress=None) -> SyncStats:
    """Store new or changed docs; with full=True, delete stored docs in scope that weren't seen.

    scope_sql picks the stored documents this sync is responsible for, e.g.
    "source = 'handbook'" or "access_id = ANY(%s)".
    """
    known = dict(conn.execute(f"SELECT source || ':' || external_id, content_hash FROM documents WHERE {scope_sql}",
                              scope_params).fetchall())
    stats, seen = SyncStats(), set()
    pending, pending_chunks = [], 0

    for doc in docs:
        key = f"{doc.source}:{doc.external_id}"
        seen.add(key)
        stats.seen += 1
        if known.get(key) == doc.content_hash:
            stats.unchanged += 1
            continue
        chunks = doc.make_chunks()
        if not chunks:
            stats.empty += 1
            continue
        pending.append((doc, chunks))
        pending_chunks += len(chunks)
        stats.changed += 1
        if pending_chunks >= GROUP_CHUNKS:
            stats.chunks += _flush(conn, pending)
            pending, pending_chunks = [], 0
            if progress:
                progress(stats)
    if pending:
        stats.chunks += _flush(conn, pending)

    if full:
        gone = [key for key in known if key not in seen]
        for key in gone:
            source, external_id = key.split(":", 1)
            conn.execute("DELETE FROM documents WHERE source = %s AND external_id = %s", (source, external_id))
        stats.deleted = len(gone)
    return stats
