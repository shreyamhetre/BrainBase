"""Permission checks against the real index: restricted chunks never reach someone without the role.

Needs the database with synced connectors and loads the embedding and reranker models
(about 20 s), so it only runs with GITMORE_INTEGRATION=1:
    GITMORE_INTEGRATION=1 python -m unittest discover -s backend/tests
"""

import os
import unittest

INTEGRATION = os.getenv("GITMORE_INTEGRATION") == "1"

# question → (roles that must NOT see restricted results, roles that should)
CASES = {
    "What are the 2027 salary bands?": (["engineer"], ["hr"]),
    "What happened with the CI job token exposed in a public fork?": (["engineer", "hr"], ["security"]),
    "What is the Q3 team restructuring plan?": (["engineer", "sales"], ["manager"]),
}


@unittest.skipUnless(INTEGRATION, "set GITMORE_INTEGRATION=1 to run against the database")
class NoLeaks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.db.connection import connect
        from app.retrieval.retrieve import retrieve
        cls.conn = connect()
        cls.retrieve = staticmethod(retrieve)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def visible_roles(self, chunk_ids: list[int]) -> list[list[str]]:
        rows = self.conn.execute("SELECT allowed_roles FROM chunks WHERE id = ANY(%s)", (chunk_ids,)).fetchall()
        return [r[0] for r in rows]

    def test_every_result_is_allowed_for_the_asker(self):
        for question, (blocked, allowed) in CASES.items():
            for roles in [[r] for r in blocked + allowed] + [[]]:
                with self.subTest(question=question, roles=roles):
                    found = self.retrieve(self.conn, question, roles)
                    for chunk_roles in self.visible_roles([c.chunk_id for c in found]):
                        self.assertTrue(set(chunk_roles) & (set(roles) | {"all"}),
                                        f"{roles} saw a chunk for {chunk_roles}")

    def test_the_right_role_does_find_it(self):
        for question, (_, allowed) in CASES.items():
            with self.subTest(question=question):
                found = self.retrieve(self.conn, question, allowed)
                self.assertTrue(any(c.source != "handbook" for c in found), f"{allowed} found no restricted source")


if __name__ == "__main__":
    unittest.main()
