"""Load selected handbook pages into Postgres: one documents row per page, its chunks
with BGE-M3 embeddings.

- Pages whose content_hash hasn't changed are skipped, so re-runs are cheap.
- Pages are embedded in groups, so the GPU gets full batches instead of one page at a time.
- A full run (no --sections / --limit) also deletes pages that are no longer selected.

Usage (from the project root):
    python -m app.ingestion.ingest_handbook                                  # everything
    python -m app.ingestion.ingest_handbook --sections people-group,hiring   # some sections
    python -m app.ingestion.ingest_handbook --limit 50                       # first 50 pages
"""

import argparse
import hashlib
import json
import time

import psycopg
from pgvector.psycopg import register_vector

from app.config import DATABASE_URL
from app.embedding import embed
from app.ingestion.chunker import CHUNKER_VERSION, Chunk
from app.ingestion.handbook import CONTENT, HandbookPage, load_page, selected_pages

SOURCE = "handbook"
DEFAULT_ROLES = ["all"]       # role-based permissions arrive in step 6
GROUP_CHUNKS = 256            # embed this many chunks per GPU round


def content_hash(page: HandbookPage) -> str:
    parts = [CHUNKER_VERSION, page.title, page.url, page.status or "",
             page.updated_at.isoformat() if page.updated_at else "", page.body]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def write_page(conn: psycopg.Connection, page: HandbookPage, digest: str, chunks: list[Chunk], vectors) -> None:
    with conn.transaction():
        doc_id = conn.execute(
            """
            INSERT INTO documents (source, external_id, title, url, section, doc_type, status,
                                   owners, allowed_roles, updated_at, content_hash, metadata, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (source, external_id) DO UPDATE SET
                title = EXCLUDED.title, url = EXCLUDED.url, section = EXCLUDED.section,
                doc_type = EXCLUDED.doc_type, status = EXCLUDED.status, owners = EXCLUDED.owners,
                allowed_roles = EXCLUDED.allowed_roles, updated_at = EXCLUDED.updated_at,
                content_hash = EXCLUDED.content_hash, metadata = EXCLUDED.metadata, synced_at = now()
            RETURNING id
            """,
            (SOURCE, page.rel_path, page.title, page.url, page.section, page.doc_type, page.status,
             page.owners, DEFAULT_ROLES, page.updated_at, digest,
             json.dumps({"description": page.description, "dropped_shortcodes": page.dropped_shortcodes})),
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
                     SOURCE, page.section, page.status, DEFAULT_ROLES, page.updated_at, c.people)
                    for i, c in enumerate(chunks)
                ],
            )


def flush(conn: psycopg.Connection, pending: list[tuple[HandbookPage, str, list[Chunk]]]) -> int:
    texts = [chunk.embed_text for _, _, chunks in pending for chunk in chunks]
    vectors = embed(texts)
    offset = 0
    for page, digest, chunks in pending:
        write_page(conn, page, digest, chunks, vectors[offset:offset + len(chunks)])
        offset += len(chunks)
    return len(texts)


def run(sections: str | None = None, limit: int | None = None, log=print) -> dict:
    """Ingest the selected pages; returns counts. Called by the script below and by the app's Refresh handbook."""
    paths = selected_pages()
    if sections:
        wanted = set(sections.split(","))
        paths = [p for p in paths if p.relative_to(CONTENT).parts[0] in wanted]
    if limit:
        paths = paths[:limit]
    full_run = not sections and not limit

    start = time.perf_counter()
    stats = {"embedded_pages": 0, "chunks": 0, "unchanged": 0, "empty": 0, "deleted": 0}

    with psycopg.connect(DATABASE_URL) as conn:
        register_vector(conn)
        known = dict(conn.execute(
            "SELECT external_id, content_hash FROM documents WHERE source = %s", (SOURCE,)
        ).fetchall())

        log(f"Pages to check: {len(paths)}  (already in database: {len(known)})")
        pending, pending_chunks = [], 0
        for n, path in enumerate(paths, 1):
            page = load_page(path)
            digest = content_hash(page)
            if known.get(page.rel_path) == digest:
                stats["unchanged"] += 1
                continue
            chunks = page.chunks()
            if not chunks:
                stats["empty"] += 1
                continue

            pending.append((page, digest, chunks))
            pending_chunks += len(chunks)
            if pending_chunks >= GROUP_CHUNKS:
                stats["chunks"] += flush(conn, pending)
                stats["embedded_pages"] += len(pending)
                pending, pending_chunks = [], 0
                rate = stats["chunks"] / (time.perf_counter() - start)
                log(f"  {n}/{len(paths)} pages checked, {stats['chunks']} chunks stored ({rate:.0f} chunks/s)")

        if pending:
            stats["chunks"] += flush(conn, pending)
            stats["embedded_pages"] += len(pending)

        if full_run:
            selected = {p.relative_to(CONTENT).as_posix() for p in paths}
            gone = [external_id for external_id in known if external_id not in selected]
            if gone:
                conn.execute(
                    "DELETE FROM documents WHERE source = %s AND external_id = ANY(%s)", (SOURCE, gone)
                )
            stats["deleted"] = len(gone)

    stats["pages"] = len(paths)
    stats["minutes"] = round((time.perf_counter() - start) / 60, 1)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sections", help="comma-separated top-level sections, e.g. people-group,hiring")
    parser.add_argument("--limit", type=int, help="only the first N selected pages")
    args = parser.parse_args()
    stats = run(args.sections, args.limit)
    print(f"\nDone in {stats['minutes']} min: {stats['embedded_pages']} pages embedded "
          f"({stats['chunks']} chunks), {stats['unchanged']} unchanged, "
          f"{stats['empty']} empty, {stats['deleted']} deleted")


if __name__ == "__main__":
    main()
