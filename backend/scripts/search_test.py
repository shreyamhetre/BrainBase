"""Run sample questions through vector search and keyword search separately, and show
where the expected page lands in each. A first look at retrieval before step 3 adds
hybrid search, RRF and reranking.

Usage: python backend/scripts/search_test.py
"""

import psycopg
from pgvector.psycopg import register_vector

from app.config import DATABASE_URL
from app.embedding import embed

TOP_K = 5
SEARCH_DEPTH = 50  # how far down to look for the expected page

# (question, keyword query, pages that correctly answer it)
QUESTIONS = [
    ("How many weeks of parental leave do I get?", "parental leave weeks",
     ["people-group/time-off-and-absence/leave-types.md"]),
    ("How does paid time off work at GitLab?", "paid time off",
     ["people-group/time-off-and-absence/time-off-types.md", "people-group/time-off-and-absence/_index.md"]),
    ("What are GitLab's core values?", "values CREDIT", ["values/_index.md"]),
    ("How do I get my merge request reviewed and merged?", "merge request review",
     ["engineering/workflow/code-review.md"]),
    ("How do I report a security incident?", "report security incident",
     ["security/engaging-with-security.md", "security/security-operations/sirt/_index.md"]),
    ("What is the expense policy for a new laptop?", "laptop expense", ["finance/expenses.md"]),
]

VECTOR_SQL = """
    SELECT d.external_id, c.heading_path, 1 - (c.embedding <=> %(v)s) AS score
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE 'all' = ANY(c.allowed_roles)
    ORDER BY c.embedding <=> %(v)s
    LIMIT %(n)s
"""

KEYWORD_SQL = """
    SELECT d.external_id, c.heading_path, ts_rank_cd(c.search_tsv, q) AS score
    FROM chunks c JOIN documents d ON d.id = c.document_id,
         websearch_to_tsquery('english', %(q)s) q
    WHERE c.search_tsv @@ q AND 'all' = ANY(c.allowed_roles)
    ORDER BY score DESC
    LIMIT %(n)s
"""


def first_hit(rows, expected: list[str]) -> int | None:
    return next((i + 1 for i, row in enumerate(rows) if row[0] in expected), None)


def main() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        register_vector(conn)
        total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
        print(f"Searching {total:,} chunks\n")

        hits = {"vector": 0, "keyword": 0}
        for question, keywords, expected in QUESTIONS:
            vector_rows = conn.execute(VECTOR_SQL, {"v": embed([question])[0], "n": SEARCH_DEPTH}).fetchall()
            keyword_rows = conn.execute(KEYWORD_SQL, {"q": keywords, "n": SEARCH_DEPTH}).fetchall()

            print(f"Q: {question}\n   expected: {', '.join(expected)}")
            for name, rows in (("vector", vector_rows), ("keyword", keyword_rows)):
                rank = first_hit(rows, expected)
                hits[name] += rank is not None and rank <= TOP_K
                found = f"rank {rank}" if rank else f"not in top {SEARCH_DEPTH}"
                print(f"   {name:<8} expected page: {found}")
                for external_id, heading, score in rows[:3]:
                    print(f"            {score:.3f}  {heading[:80]}")
            print()

        n = len(QUESTIONS)
        print(f"Expected page in top {TOP_K}: vector {hits['vector']}/{n}, keyword {hits['keyword']}/{n}")


if __name__ == "__main__":
    main()
