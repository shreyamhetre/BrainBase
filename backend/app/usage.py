"""Permanent usage log: one row per message, written whether or not Langfuse is running."""

import json

from app.config import LLM_MODEL, LLM_PRICE_INPUT_PER_M, LLM_PRICE_OUTPUT_PER_M
from app.db.connection import connect
from app.generation.answer import NOT_FOUND


def cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * LLM_PRICE_INPUT_PER_M + completion_tokens * LLM_PRICE_OUTPUT_PER_M) / 1_000_000


def log_question(user_id: str | None, message: str, reply, seconds: float) -> None:
    """reply is a graph.Reply: an answer, a proposed action or a clarifying question."""
    cited = set(reply.answer.cited) if reply.answer else set()
    sources = [{"source": c.source, "title": c.heading_path, "link": c.link, "cited": n in cited}
               for n, c in enumerate(reply.sources, 1)]
    found = not (reply.kind == "answer" and NOT_FOUND.rstrip(".") in reply.text)
    text = f"[{reply.kind}] {reply.text}" if reply.kind != "answer" else reply.text
    used = {id(c) for c in reply.sources}
    details = {"chunks": [_chunk(n, c, id(c) in used and (n in cited)) for n, c in enumerate(getattr(reply, "retrieved", []) or [], 1)]}
    if reply.action:
        details["action"] = {"tool": reply.action.get("tool"), "server": reply.action.get("server"),
                             "summary": reply.action.get("summary"), "target": reply.action.get("target")}
    with connect() as conn:
        conn.execute(
            "INSERT INTO query_log (user_id, question, answer, found, sources, model, prompt_tokens, completion_tokens, "
            "cost_usd, seconds, trace_id, trace_url, route, search_question, details) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, message, text, found, json.dumps(sources), LLM_MODEL, reply.prompt_tokens, reply.completion_tokens,
             cost_usd(reply.prompt_tokens, reply.completion_tokens), seconds, reply.trace_id, reply.trace_url,
             reply.kind, getattr(reply, "search_question", "") or None, json.dumps(details)),
        )


def _chunk(rank: int, c, cited: bool) -> dict:
    """One retrieved chunk with every score the pipeline gave it."""
    def num(x):
        return round(float(x), 4) if x is not None else None
    return {"rank": rank, "source": c.source, "title": c.title, "heading_path": c.heading_path, "link": c.link,
            "updated_at": c.updated_at.date().isoformat() if c.updated_at else None, "cited": cited,
            "vector_rank": c.vector_rank, "vector_score": num(c.vector_score), "keyword_rank": c.keyword_rank,
            "keyword_score": num(c.keyword_score), "rrf_score": num(c.rrf_score), "rerank_score": num(c.rerank_score),
            "preview": c.content[:300]}
