"""The full retrieval pipeline: hybrid search → RRF → rerank → top chunks."""

import psycopg

from app import rag_settings
from app.retrieval.rank import rerank, rrf_merge
from app.retrieval.search import Candidate, hybrid_search


def retrieve(conn: psycopg.Connection, question: str, roles: list[str], top_k: int | None = None) -> list[Candidate]:
    """Numbers come from the RAG settings (Admin console), so admins can tune them without a deploy."""
    s = rag_settings.get()
    candidates = hybrid_search(conn, question, roles, s.candidates_per_search)
    merged = rrf_merge(candidates)
    return rerank(question, merged[:s.rerank_pool], top_k or s.final_k)
