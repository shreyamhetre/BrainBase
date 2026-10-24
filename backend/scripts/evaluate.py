"""Evaluate GitMore on the questions in eval/questions.md.

For each question: ask GitMore, then score
- retrieval (in code): is an expected page among the sources (hit@5), at which rank (MRR),
  and does the answer cite it;
- the answer (GPT-4o mini as judge): is every claim supported by its cited sources
  (faithful), and does it answer the question and meet the question's check (correct).
No-answer questions pass when GitMore says it couldn't find the answer.

Writes eval/results/<timestamp>.json and prints a row for the Results table.

Usage: python backend/scripts/evaluate.py --note "baseline"
"""

import argparse
import json
import re
import statistics
import time
from dataclasses import dataclass
from datetime import datetime

from langfuse import get_client as get_langfuse

from app.config import LLM_MODEL, PROJECT_ROOT
from app.embedding import get_model
from app.generation.answer import NOT_FOUND, format_sources, get_client
from app.graph import ask_as
from app.retrieval.rank import get_reranker

QUESTIONS_FILE = PROJECT_ROOT / "eval" / "questions.md"
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"
BASE_URL = "https://handbook.gitlab.com/handbook/"
ROW = re.compile(r"^\|\s*(\d+)\s*\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s*$")

JUDGE_PROMPT = """You grade answers from a RAG assistant that must answer only from its numbered sources.

Return JSON with these keys:
- "faithful": true if every factual claim in the answer is supported by the source it cites \
(or by some source when uncited). false if any claim is missing from the sources, contradicts \
them, or is attributed to the wrong scope (for example a global rule presented as one country's rule).
- "unsupported_claims": list of the claims that are not supported (empty if faithful).
- "correct": true if the answer actually answers the question and satisfies the check.
- "reason": one or two sentences explaining both grades.

Be strict: a single unsupported or mis-scoped claim makes "faithful" false."""


@dataclass
class Question:
    number: int
    category: str
    text: str
    expected: list[str]   # page paths; empty for no-answer questions
    check: str


def load_questions() -> list[Question]:
    questions = []
    for line in QUESTIONS_FILE.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if not match:
            continue
        number, category, text, expected, check = (part.strip() for part in match.groups())
        pages = [] if expected.lower() == "none" else [p.strip().strip("/") for p in expected.split(",")]
        questions.append(Question(int(number), category, text, pages, check))
    return questions


def page_path(url: str) -> str:
    return url.removeprefix(BASE_URL).strip("/")


def judge(question: Question, answer) -> dict:
    response = get_client().chat.completions.create(
        name="judge",
        model=LLM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": (
                f"Question: {question.text}\n\nCheck: {question.check}\n\n"
                f"Sources:\n\n{format_sources(answer.sources)}\n\nAnswer to grade:\n{answer.text}"
            )},
        ],
    )
    return json.loads(response.choices[0].message.content)


def evaluate(question: Question) -> dict:
    start = time.perf_counter()
    answer = ask_as(question.text, ["all"])
    seconds = time.perf_counter() - start

    pages = [page_path(c.url) for c in answer.sources]
    rank = next((i + 1 for i, p in enumerate(pages) if p in question.expected), None)
    said_not_found = NOT_FOUND.lower().rstrip(".") in answer.text.lower()

    if question.expected:
        verdict = judge(question, answer)
        cited = any(pages[n - 1] in question.expected for n in answer.cited)
    else:  # no-answer question: passing means admitting it, without inventing anything
        verdict = {"faithful": said_not_found, "correct": said_not_found, "unsupported_claims": [],
                   "reason": "said it couldn't find this" if said_not_found else "gave an answer instead"}
        cited = None

    return {
        "number": question.number, "category": question.category, "question": question.text,
        "expected": question.expected, "rank": rank, "cited_expected": cited,
        "said_not_found": said_not_found, "faithful": bool(verdict["faithful"]),
        "correct": bool(verdict["correct"]), "unsupported_claims": verdict.get("unsupported_claims", []),
        "reason": verdict.get("reason", ""), "answer": answer.text,
        "sources": [{"n": n, "page": p, "heading": c.heading_path, "cited": n in answer.cited}
                    for n, (p, c) in enumerate(zip(pages, answer.sources), 1)],
        "seconds": round(seconds, 2), "prompt_tokens": answer.prompt_tokens,
        "completion_tokens": answer.completion_tokens,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note", default="", help="what changed since the last run")
    args = parser.parse_args()

    get_model()
    get_reranker()
    questions = load_questions()
    print(f"Evaluating {len(questions)} questions\n")

    results = []
    for q in questions:
        r = evaluate(q)
        results.append(r)
        rank = f"rank {r['rank']}" if r["rank"] else ("n/a" if not q.expected else "MISS")
        flags = " ".join(f"{name}={'✓' if r[key] else '✗'}" for name, key in
                         (("faithful", "faithful"), ("correct", "correct")))
        print(f"{q.number:>2}. [{q.category}] {q.text}\n    source {rank} | {flags} | {r['seconds']} s")
        if not (r["faithful"] and r["correct"]):
            print(f"    → {r['reason']}")
            for claim in r["unsupported_claims"]:
                print(f"      unsupported: {claim}")

    answerable = [r for r in results if r["expected"]]
    no_answer = [r for r in results if not r["expected"]]
    summary = {
        "hit_at_5": sum(r["rank"] is not None for r in answerable),
        "mrr": round(statistics.mean(1 / r["rank"] if r["rank"] else 0 for r in answerable), 2),
        "cited": sum(bool(r["cited_expected"]) for r in answerable),
        "faithful": sum(r["faithful"] for r in results),
        "correct": sum(r["correct"] for r in results),
        "no_answer": sum(r["said_not_found"] for r in no_answer),
        "avg_seconds": round(statistics.mean(r["seconds"] for r in results), 1),
        "tokens": sum(r["prompt_tokens"] + r["completion_tokens"] for r in results),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now()
    out = RESULTS_DIR / f"{stamp:%Y-%m-%d_%H%M}.json"
    out.write_text(json.dumps({"date": stamp.isoformat(timespec="minutes"), "note": args.note,
                               "summary": summary, "results": results}, indent=2), encoding="utf-8")

    a, n, total = len(answerable), len(no_answer), len(results)
    print(f"\nHit@5 {summary['hit_at_5']}/{a} | MRR {summary['mrr']} | cited {summary['cited']}/{a} | "
          f"faithful {summary['faithful']}/{total} | correct {summary['correct']}/{total} | "
          f"no-answer {summary['no_answer']}/{n} | {summary['avg_seconds']} s avg | {summary['tokens']:,} tokens")
    print(f"Saved {out.relative_to(PROJECT_ROOT)}\n\nResults table row:")
    print(f"| {stamp:%Y-%m-%d} | {args.note} | {summary['hit_at_5']}/{a} | {summary['mrr']} | "
          f"{summary['cited']}/{a} | {summary['faithful']}/{total} | {summary['correct']}/{total} | "
          f"{summary['no_answer']}/{n} | {summary['avg_seconds']} s | |")
    get_langfuse().flush()


if __name__ == "__main__":
    main()
