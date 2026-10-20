"""The full retrieval pipeline: hybrid search → RRF → rerank → top chunks."""

import psycopg

from app.retrieval.rank import FINAL_K, RERANK_POOL, rerank, rrf_merge
from app.retrieval.search import Candidate, hybrid_search


def retrieve(conn: psycopg.Connection, question: str, roles: list[str], top_k: int = FINAL_K) -> list[Candidate]:
    candidates = hybrid_search(conn, question, roles)
    merged = rrf_merge(candidates)
    return rerank(question, merged[:RERANK_POOL], top_k)
