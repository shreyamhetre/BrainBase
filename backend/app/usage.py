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
    with connect() as conn:
        conn.execute(
            "INSERT INTO query_log (user_id, question, answer, found, sources, model, prompt_tokens, completion_tokens, "
            "cost_usd, seconds, trace_id, trace_url) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, message, text, found, json.dumps(sources), LLM_MODEL, reply.prompt_tokens, reply.completion_tokens,
             cost_usd(reply.prompt_tokens, reply.completion_tokens), seconds, reply.trace_id, reply.trace_url),
        )
