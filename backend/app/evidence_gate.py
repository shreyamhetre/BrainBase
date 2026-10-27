"""Jev evidence gate: before GPT answers, Jev (TypeSafe's System One model) checks whether the
reranked sources contain enough evidence to answer the question.

    search → rerank → Jev: enough evidence?
        yes → GPT answers with citations
        no  → GPT rewrites the question → search → rerank → Jev again
                  yes → GPT answers
                  no  → "I couldn't find this in the sources you can access."  (no answer call)

One retry only. Jev gets small, trimmed evidence (title, type, date and the start of each
source), and what it saw and decided is kept for the query inspector.

If Jev is unreachable or the key is missing, the gate stays out of the way: the answer is
written as before and the inspector says why the gate was skipped.
"""

import time
from dataclasses import asdict, dataclass, field

import httpx
from langfuse import observe

from app import rag_settings
from app.config import TYPESAFE_API_KEY
from app.generation.answer import get_client
from app.retrieval.search import Candidate

URL = "https://api.typesafe.ai/v1/systemone"
TRIM = 1200          # characters of each source Jev reads; enough to judge, cheap to send
TIMEOUT = 15.0

ENOUGH = {
    "type": "noul",
    "instructions": "Do the sources together contain enough information to answer the question?",
    "criteria": {
        "true": "At least one source states the facts the question asks for, so a direct answer can be written from the sources alone",
        "false": "The sources are about something else, only mention the topic in passing, or leave out the facts the question asks for",
    },
}

REWRITE_PROMPT = """A company knowledge search found too little evidence for this question.
Rewrite it as one different search query that is more likely to find the answer in a company handbook,
Slack threads or GitLab issues: use the formal policy or process terms, spell out abbreviations,
and keep every name, number and date from the question. Never add placeholders such as [Company Name]
or words the question didn't imply. Reply with the query only."""


@dataclass
class Check:
    question: str                               # what was searched
    enough: float | None = None                 # Jev's probability that the sources are enough
    passed: bool = False
    per_source: list[float | None] = field(default_factory=list)   # does source n help? (same order as the chunks)
    sent: list[dict] = field(default_factory=list)                 # the trimmed evidence Jev read
    input_tokens: int = 0
    seconds: float = 0.0
    error: str = ""


@dataclass
class GateResult:
    chunks: list[Candidate]                     # the chunks to answer from ([] = couldn't find)
    question: str                               # the question the last search used
    retrieved: list[Candidate] = field(default_factory=list)   # what the last search found (for the inspector)
    checks: list[Check] = field(default_factory=list)
    rewrite_tokens: tuple[int, int] = (0, 0)    # GPT prompt / completion tokens for the rewrite
    outcome: str = "off"                        # off, skipped, passed, passed_after_retry, failed

    def details(self) -> dict:
        s = rag_settings.get()
        jev_tokens = sum(c.input_tokens for c in self.checks)
        return {"outcome": self.outcome, "threshold": s.gate_threshold, "model": s.gate_model,
                "jev_tokens": jev_tokens, "jev_cost_usd": jev_tokens * s.gate_price_per_m / 1_000_000,
                "rewrite_tokens": list(self.rewrite_tokens), "checks": [asdict(c) for c in self.checks]}


def _evidence(chunks: list[Candidate]) -> list[dict]:
    return [{"n": n, "type": c.source, "title": c.heading_path or c.title,
             "date": c.updated_at.date().isoformat() if c.updated_at else None,
             "text": c.content[:TRIM] + ("…" if len(c.content) > TRIM else "")}
            for n, c in enumerate(chunks, 1)]


@observe(name="jev-gate")
def check(question: str, chunks: list[Candidate]) -> Check:
    """One Jev request: the question plus trimmed sources, asked "enough?" and "does source n help?"."""
    s = rag_settings.get()
    result = Check(question=question, sent=_evidence(chunks))
    if not chunks:
        return result                            # nothing found: nothing to send
    questions = {"enough": ENOUGH} | {
        f"source_{n}": {"type": "noul", "instructions": f"Does source {n} contain information that helps answer the question?"}
        for n in range(1, len(chunks) + 1)}
    started = time.perf_counter()
    try:
        response = httpx.post(URL, headers={"Authorization": f"Bearer {TYPESAFE_API_KEY}"}, timeout=TIMEOUT,
                              json={"model": s.gate_model, "state": {"question": question, "sources": result.sent},
                                    "questions": questions})
        response.raise_for_status()
        body = response.json()
    except httpx.HTTPStatusError as e:
        result.error = f"Jev returned {e.response.status_code}: {e.response.text[:200]}"
    except (httpx.HTTPError, ValueError) as e:
        result.error = f"Jev unreachable: {e}"[:300]
    else:
        answers = body.get("answers", {})
        result.enough = answers.get("enough", {}).get("noul")
        result.per_source = [answers.get(f"source_{n}", {}).get("noul") for n in range(1, len(chunks) + 1)]
        result.input_tokens = (body.get("usage") or {}).get("input_tokens") or 0
        result.passed = result.enough is not None and result.enough >= s.gate_threshold
    result.seconds = round(time.perf_counter() - started, 2)
    return result


@observe(name="rewrite-question")
def rewrite(question: str) -> tuple[str, int, int]:
    """GPT writes one different search query for the same question."""
    response = get_client().chat.completions.create(
        model=rag_settings.get().llm_model, temperature=0, max_tokens=80,
        messages=[{"role": "system", "content": REWRITE_PROMPT}, {"role": "user", "content": question}])
    text = (response.choices[0].message.content or "").strip().strip('"') or question
    usage = response.usage
    return text, usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0


def gated_retrieve(retrieve_fn, question: str) -> GateResult:
    """retrieve_fn(question) -> chunks. Runs the gate around it when it's on and Jev is set up."""
    chunks = retrieve_fn(question)
    if not rag_settings.get().gate_enabled:
        return GateResult(chunks, question, chunks)
    if not TYPESAFE_API_KEY:
        return GateResult(chunks, question, chunks, [Check(question, error="TYPESAFE_API_KEY is not set in .env")], outcome="skipped")

    first = check(question, chunks)
    if first.error:
        return GateResult(chunks, question, chunks, [first], outcome="skipped")
    if first.passed:
        return GateResult(chunks, question, chunks, [first], outcome="passed")

    retry_question, prompt_tokens, completion_tokens = rewrite(question)
    retry_chunks = retrieve_fn(retry_question)
    second = check(retry_question, retry_chunks)
    result = GateResult(retry_chunks, retry_question, retry_chunks, [first, second], (prompt_tokens, completion_tokens))
    if second.error:
        result.outcome = "skipped"                # Jev failed on the retry: answer from the retry's sources
    elif second.passed:
        result.outcome = "passed_after_retry"
    else:
        result.chunks, result.outcome = [], "failed"
    return result
