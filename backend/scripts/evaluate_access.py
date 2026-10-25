"""Permission, routing, conflict and cross-source checks, asked as real demo people.

Cases live in eval/access_questions.json:
- leak:     nothing the person may not read appears in the sources or the answer (target: zero leaks)
- find:     someone with the right role does reach the restricted source
- route:    the router picks chat, answer, action, choose (with the right tool) or clarify
- conflict: the PTO answer gives the handbook rule and names the older Slack answer
- cross:    the answer draws on more than one tool (issues and Slack)

Modes:
    python backend/scripts/evaluate_access.py --quick            # 9 key cases (about 20k tokens)
    python backend/scripts/evaluate_access.py --retrieval-only   # leak and find cases, search only: no GPT calls, free
    python backend/scripts/evaluate_access.py                    # everything, through the real chat flow

Proposed actions are cancelled at once, so nothing is ever posted to GitLab. Results are saved
to eval/results/access_<date>.json.
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from app.auth import User, get_user, search_roles
from app.config import PROJECT_ROOT
from app.db.connection import connect
from app.retrieval.retrieve import retrieve

CASES = PROJECT_ROOT / "eval" / "access_questions.json"
# One or two of each kind: leaks, finding, GitLab and Slack actions, chat, the guardrail, explain-or-do, the conflict
QUICK = ["L1", "L2", "F1", "R2", "R8", "R10", "R12", "R14", "C1"]
RESULTS = PROJECT_ROOT / "eval" / "results"
NEW_SIGNUP = User("00000000-0000-0000-0000-000000000000", "new@gitmore.com", "New Sign-up", [], False, None, None)


def person(email: str) -> User:
    if email == "tmp-new-signup":
        return NEW_SIGNUP
    with connect() as conn:
        row = conn.execute("SELECT id::text FROM users WHERE email = %s", (email,)).fetchone()
    user = get_user(row[0]) if row else None
    if not user:
        raise SystemExit(f"No active user {email}; run backend/scripts/seed_users.py")
    return user


def chunk_roles(conn, chunk_ids: list[int]) -> dict[int, list[str]]:
    return dict(conn.execute("SELECT id, allowed_roles FROM chunks WHERE id = ANY(%s)", (chunk_ids,)).fetchall())


def leaked(conn, user: User, sources) -> list[str]:
    """Sources the person may not read. Must always be empty."""
    allowed = set(search_roles(user)) | {"all"}
    roles = chunk_roles(conn, [s.chunk_id for s in sources])
    return [f"{s.source}:{s.title}" for s in sources if not set(roles.get(s.chunk_id, [])) & allowed]


def check_retrieval(case: dict, user: User) -> dict:
    with connect() as conn:
        sources = retrieve(conn, case["message"], search_roles(user))
        leaks = leaked(conn, user, sources)
    kinds = sorted({s.source for s in sources})
    problems = [f"leaked {x}" for x in leaks]
    if case["type"] == "find" and not set(case["expect_sources"]) & set(kinds):
        problems.append(f"didn't reach {case['expect_sources']} (got {kinds})")
    return {"sources": kinds, "problems": problems}


def check_full(case: dict, user: User) -> dict:
    from app.graph import ask

    reply = ask(case["message"], user)
    if reply.action:  # never post anything during evaluation
        with connect() as conn:
            conn.execute("UPDATE actions SET status = 'cancelled', decided_at = now() WHERE id = %s", (reply.action["id"],))
    with connect() as conn:
        leaks = leaked(conn, user, reply.sources)
    text = reply.text
    kinds = sorted({s.source for s in reply.sources})
    problems = [f"leaked {x}" for x in leaks]
    t = case["type"]
    if t == "leak":
        problems += [f"answer contains '{x}'" for x in case.get("forbidden_text", []) if x.lower() in text.lower()]
        if case.get("expect_not_found") and "couldn't find" not in text.lower():
            problems.append("expected 'couldn't find'")
    if t in ("find", "cross") and not set(case["expect_sources"]) & set(kinds):
        problems.append(f"didn't use {case['expect_sources']} (got {kinds})")
    if t == "cross" and len(set(case["expect_sources"]) & set(kinds)) < 2:
        problems.append(f"expected both {case['expect_sources']} (got {kinds})")
    if t == "route":
        if reply.kind != case["expect_route"]:
            problems.append(f"route {reply.kind}, expected {case['expect_route']}")
        elif case.get("expect_tool") and (reply.action or {}).get("tool") != case["expect_tool"]:
            problems.append(f"tool {(reply.action or {}).get('tool')}, expected {case['expect_tool']}")
        if case.get("expect_offer") and reply.offer_tool != case["expect_offer"]:
            problems.append(f"offered {reply.offer_tool or 'nothing'}, expected {case['expect_offer']}")
        if reply.kind == "chat" and reply.sources:
            problems.append("a chat reply came with sources")
    if t == "conflict":
        problems += [f"answer lacks '{x}'" for x in case["expect_text"] + case["expect_mention"] if x.lower() not in text.lower()]
    return {"route": reply.kind, "sources": kinds, "answer": text[:500], "problems": problems,
            "tokens": reply.prompt_tokens + reply.completion_tokens}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--retrieval-only", action="store_true", help="leak and find cases through search only (no GPT calls)")
    parser.add_argument("--only", help="comma-separated case ids, e.g. L1,R2")
    parser.add_argument("--quick", action="store_true", help=f"only the key cases: {', '.join(QUICK)}")
    args = parser.parse_args()

    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] in args.only.split(",")]
    if args.quick:
        cases = [c for c in cases if c["id"] in QUICK]
    if args.retrieval_only:
        cases = [c for c in cases if c["type"] in ("leak", "find")]

    results, start = [], time.perf_counter()
    for case in cases:
        user = person(case["as"])
        result = check_retrieval(case, user) if args.retrieval_only else check_full(case, user)
        results.append({"id": case["id"], "type": case["type"], "as": user.name, "message": case["message"], **result})
        mark = "PASS" if not result["problems"] else "FAIL"
        print(f"{mark}  {case['id']:<3} {case['type']:<8} {user.name:<18} {case['message'][:58]}")
        for p in result["problems"]:
            print(f"        - {p}")

    leaks = sum(1 for r in results for p in r["problems"] if p.startswith("leaked") or p.startswith("answer contains"))
    passed = sum(1 for r in results if not r["problems"])
    by_type = {}
    for r in results:
        t = by_type.setdefault(r["type"], [0, 0])
        t[0] += not r["problems"]
        t[1] += 1
    tokens = sum(r.get("tokens", 0) for r in results)
    summary = {"mode": "retrieval-only" if args.retrieval_only else "quick" if args.quick else "full", "passed": passed, "total": len(results),
               "leaks": leaks, "by_type": {k: f"{a}/{b}" for k, (a, b) in by_type.items()}, "tokens": tokens,
               "seconds": round(time.perf_counter() - start, 1)}
    print(f"\n{passed}/{len(results)} passed · leaks: {leaks} · " + " · ".join(f"{k} {v}" for k, v in summary["by_type"].items())
          + (f" · {tokens} tokens" if tokens else ""))

    RESULTS.mkdir(parents=True, exist_ok=True)
    suffix = "_retrieval" if args.retrieval_only else "_quick" if args.quick else ""
    out = RESULTS / f"access_{datetime.now():%Y-%m-%d_%H%M}{suffix}.json"
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")
    print(f"Saved {out.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
