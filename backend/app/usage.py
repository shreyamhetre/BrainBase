"""Permanent usage log: one row per question, written whether or not Langfuse is running."""

import json

from app.config import LLM_MODEL, LLM_PRICE_INPUT_PER_M, LLM_PRICE_OUTPUT_PER_M
from app.db.connection import connect
from app.generation.answer import NOT_FOUND, Answer


def cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * LLM_PRICE_INPUT_PER_M + completion_tokens * LLM_PRICE_OUTPUT_PER_M) / 1_000_000


def log_question(user_id: str | None, question: str, answer: Answer, seconds: float) -> None:
    sources = [{"source": c.source, "title": c.heading_path, "link": c.link, "cited": n in answer.cited}
               for n, c in enumerate(answer.sources, 1)]
    with connect() as conn:
        conn.execute(
            "INSERT INTO query_log (user_id, question, answer, found, sources, model, prompt_tokens, completion_tokens, "
            "cost_usd, seconds, trace_id, trace_url) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (user_id, question, answer.text, NOT_FOUND.rstrip(".") not in answer.text, json.dumps(sources), LLM_MODEL,
             answer.prompt_tokens, answer.completion_tokens, cost_usd(answer.prompt_tokens, answer.completion_tokens),
             seconds, answer.trace_id, answer.trace_url),
        )
