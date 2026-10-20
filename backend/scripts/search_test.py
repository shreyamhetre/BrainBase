"""Run sample questions through hybrid search and show where the expected page lands
in the vector list and the keyword list. A baseline before RRF and reranking.

Usage: python backend/scripts/search_test.py
"""

import time

from app.db.connection import connect
from app.embedding import get_model
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
    get_model()  # load the model up front so timings below are search only
    hits = {"vector": 0, "keyword": 0}

    with connect() as conn:
        total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
        print(f"Searching {total:,} chunks, top {CANDIDATES_PER_SEARCH} per search\n")

        for question, expected in QUESTIONS:
            start = time.perf_counter()
            candidates = hybrid_search(conn, question, ROLES)
            ms = (time.perf_counter() - start) * 1000

            lists = {
                "vector": sorted((c for c in candidates if c.vector_rank), key=lambda c: c.vector_rank),
                "keyword": sorted((c for c in candidates if c.keyword_rank), key=lambda c: c.keyword_rank),
            }
            both = sum(1 for c in candidates if c.vector_rank and c.keyword_rank)
            print(f"Q: {question}  ({ms:.0f} ms, {len(candidates)} candidates, {both} in both lists)")
            for name, ranked in lists.items():
                rank = expected_rank(ranked, expected)
                hits[name] += rank is not None and rank <= TOP_K
                print(f"   {name:<8} expected page: {f'rank {rank}' if rank else 'not found'}"
                      f"   | top: {ranked[0].heading_path[:70] if ranked else '-'}")
            print()

    n = len(QUESTIONS)
    print(f"Expected page in top {TOP_K}: vector {hits['vector']}/{n}, keyword {hits['keyword']}/{n}")


if __name__ == "__main__":
    main()
