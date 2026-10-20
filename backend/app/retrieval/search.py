"""Hybrid search: vector search (meaning) and keyword search (exact words) in one SQL query.

Both searches apply the permission filter in their WHERE clause, so restricted chunks
are never retrieved. Each returns its own top `k`; a chunk can appear in either list
or both. Merging the two lists (RRF) and reranking happen in the next stage.
"""

from dataclasses import dataclass
from datetime import datetime

import psycopg

from app.embedding import embed

CANDIDATES_PER_SEARCH = 50

# Keyword search: chunks containing all of the question's words (after stop words are
# removed and words are stemmed) rank first; chunks with only some of them fill the rest.
# Postgres ranking ignores how common a word is, so ranking by "any word" alone lets
# frequent words like "gitlab" dominate. ts_rank_cd normalization 1 divides by
# 1 + log(length), so long chunks don't win just by repeating words.
HYBRID_SQL = """
WITH
vec AS (
    SELECT id, row_number() OVER (ORDER BY dist) AS rank, 1 - dist AS score
    FROM (
        SELECT c.id, c.embedding <=> %(vector)s AS dist
        FROM chunks c
        WHERE c.allowed_roles && %(roles)s
        ORDER BY dist
        LIMIT %(k)s
    ) nearest
),
query AS (
    SELECT plainto_tsquery('english', %(question)s) AS all_words,
           to_tsquery('english', replace(plainto_tsquery('english', %(question)s)::text, ' & ', ' | ')) AS any_word
),
kw AS (
    SELECT id, row_number() OVER (ORDER BY has_all DESC, score DESC) AS rank, score
    FROM (
        SELECT c.id,
               c.search_tsv @@ query.all_words AS has_all,
               ts_rank_cd(c.search_tsv, query.any_word, 1) AS score
        FROM chunks c, query
        WHERE c.search_tsv @@ query.any_word AND c.allowed_roles && %(roles)s
        ORDER BY has_all DESC, score DESC
        LIMIT %(k)s
    ) matches
)
SELECT c.id, c.document_id, d.title, d.url, c.anchor, c.heading_path, c.content, c.source,
       c.section, c.status, c.updated_at, c.people,
       vec.rank, vec.score, kw.rank, kw.score
FROM (SELECT id FROM vec UNION SELECT id FROM kw) hits
JOIN chunks c ON c.id = hits.id
JOIN documents d ON d.id = c.document_id
LEFT JOIN vec ON vec.id = c.id
LEFT JOIN kw ON kw.id = c.id
"""


@dataclass
class Candidate:
    chunk_id: int
    document_id: int
    title: str
    url: str
    anchor: str | None
    heading_path: str
    content: str
    source: str
    section: str | None
    status: str | None
    updated_at: datetime | None
    people: list[str]
    vector_rank: int | None
    vector_score: float | None
    keyword_rank: int | None
    keyword_score: float | None
    rrf_score: float = 0.0       # set by rank.rrf_merge
    rerank_score: float = 0.0    # set by rank.rerank

    @property
    def embed_text(self) -> str:
        """The same text that was embedded at ingestion: breadcrumb + content."""
        return f"{self.heading_path}\n\n{self.content}"

    @property
    def link(self) -> str:
        return f"{self.url}#{self.anchor}" if self.anchor else self.url


def hybrid_search(
    conn: psycopg.Connection, question: str, roles: list[str], k: int = CANDIDATES_PER_SEARCH
) -> list[Candidate]:
    """Top-k vector hits and top-k keyword hits for a question, visible to the given roles."""
    vector = embed([question])[0]
    allowed = sorted(set(roles) | {"all"})  # everyone can see chunks marked "all"

    with conn.transaction():
        # HNSW looks at ef_search candidates; it must be at least k or fewer than k come back.
        # Iterative scan keeps searching when the permission filter removes candidates.
        conn.execute(f"SET LOCAL hnsw.ef_search = {max(100, k * 2)}")
        conn.execute("SET LOCAL hnsw.iterative_scan = strict_order")
        rows = conn.execute(
            HYBRID_SQL, {"vector": vector, "roles": allowed, "question": question, "k": k}
        ).fetchall()

    return [Candidate(*row) for row in rows]
