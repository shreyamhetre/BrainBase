"""Run sample questions through retrieval and show where the expected page lands at
each stage: vector list, keyword list, after RRF, and after reranking.

Usage: python backend/scripts/search_test.py
"""

import time

from app.db.connection import connect
from app.embedding import get_model
from app.retrieval.rank import RERANK_POOL, get_reranker, rerank, rrf_merge
from app.retrieval.search import CANDIDATES_PER_SEARCH, Candidate, hybrid_search

TOP_K = 5
ROLES = ["all"]

# (question, pages that correctly answer it)
QUESTIONS = [
    ("How many weeks of parental leave do I get?",
     ["people-group/time-off-and-absence/leave-types.md"]),
    ("How does paid time off work at GitLab?",
     ["people-group/time-off-and-absence/time-off-types.md", "people-group/time-off-and-absence/_index.md"]),
    ("What are GitLab's core values?", ["values/_index.md"]),
    ("How do I get my merge request reviewed and merged?", ["engineering/workflow/code-review.md"]),
    ("How do I report a security incident?",
     ["security/engaging-with-security.md", "security/security-operations/sirt/_index.md"]),
    ("What is the expense policy for a new laptop?", ["finance/expenses.md"]),
]


def page_of(candidate: Candidate) -> str:
    return candidate.url.removeprefix("https://handbook.gitlab.com/handbook/")


def expected_rank(ranked: list[Candidate], expected: list[str]) -> int | None:
    expected_urls = {e.removesuffix(".md").removesuffix("_index").rstrip("/") + "/" for e in expected}
    return next((i + 1 for i, c in enumerate(ranked) if page_of(c) in expected_urls), None)


def main() -> None:
    get_model()      # load both models up front so timings below are search only
    get_reranker()
    stages = ("vector", "keyword", "rrf", "reranked")
    hits = dict.fromkeys(stages, 0)

    with connect() as conn:
        total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
        print(f"Searching {total:,} chunks: top {CANDIDATES_PER_SEARCH} per search, "
              f"reranker reads top {RERANK_POOL} after RRF\n")

        for question, expected in QUESTIONS:
            start = time.perf_counter()
            candidates = hybrid_search(conn, question, ROLES)
            search_ms = (time.perf_counter() - start) * 1000
            merged = rrf_merge(candidates)
            start = time.perf_counter()
            reranked = rerank(question, merged[:RERANK_POOL], top_k=RERANK_POOL)
            rerank_ms = (time.perf_counter() - start) * 1000

            lists = {
                "vector": sorted((c for c in candidates if c.vector_rank), key=lambda c: c.vector_rank),
                "keyword": sorted((c for c in candidates if c.keyword_rank), key=lambda c: c.keyword_rank),
                "rrf": merged,
                "reranked": reranked,
            }
            print(f"Q: {question}  (search {search_ms:.0f} ms, rerank {rerank_ms:.0f} ms)")
            ranks = []
            for name in stages:
                rank = expected_rank(lists[name], expected)
                hits[name] += rank is not None and rank <= TOP_K
                ranks.append(f"{name} {rank if rank else '-'}")
            print("   expected page rank: " + " → ".join(ranks))
            for c in reranked[:3]:
                print(f"      {c.rerank_score:.3f}  {c.heading_path[:85]}")
            print()

    n = len(QUESTIONS)
    print(f"Expected page in top {TOP_K}: " + ", ".join(f"{name} {hits[name]}/{n}" for name in stages))


if __name__ == "__main__":
    main()
