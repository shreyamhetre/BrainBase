"""Write a cited answer from the retrieved chunks with GPT-4o mini.

The model sees the chunks as numbered sources and must answer only from them, citing
each claim as [n]. The OpenAI client comes from langfuse.openai, a drop-in wrapper that
records the prompt, answer, tokens and cost of every call in Langfuse.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from langfuse.openai import OpenAI

from app.config import LLM_BASE_URL, LLM_MODEL, OPENAI_API_KEY
from app.retrieval.search import Candidate

# Says nothing about restricted content: the user can't tell whether something exists that they may not read.
NOT_FOUND = "I couldn't find this in the sources you can access."

SOURCE_TYPES = {"handbook": "Handbook page", "slack": "Slack thread", "gitlab_issue": "GitLab issue",
                "gitlab_wiki": "Wiki page", "upload": "Company document", "gitlab_file": "GitLab file"}

SYSTEM_PROMPT = f"""You are GitMore, an unofficial assistant that answers questions about GitLab \
using excerpts from the company's sources: the public handbook, Slack threads, GitLab issues and wiki pages.

Rules:
- Answer only from the numbered sources below. Do not use outside knowledge.
- Cite every claim with the source number in square brackets, like [1] or [2][3]. Only cite a source \
for something that source actually says.
- If the sources don't contain the answer, reply exactly: "{NOT_FOUND}"
- Handbook pages are official policy. Slack threads and issues are what people said or decided on a date.
- If a Slack thread or issue contradicts a handbook page, give the handbook rule, then add one sentence \
naming the conflict, for example: "An older Slack thread [1] from May 2026 said ..., but the handbook [2] \
is the current rule." Never merge the two into one answer.
- If two sources of the same kind disagree, prefer the most recently updated one and mention the difference.
- If a source is a design document with status proposed or rejected, say so; it is not \
how GitLab works today.
- If the answer differs by country or team, give the general rule first, then the differences.
- Be concise: a short paragraph or a few bullet points."""


@dataclass
class Answer:
    text: str
    sources: list[Candidate]     # numbered 1..n in the order shown to the model
    cited: list[int]             # source numbers the answer actually cites
    prompt_tokens: int
    completion_tokens: int
    trace_id: str | None = None  # Langfuse trace, set by graph.ask
    trace_url: str | None = None


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    return OpenAI(api_key=OPENAI_API_KEY, base_url=LLM_BASE_URL)


def format_sources(chunks: list[Candidate]) -> str:
    blocks = []
    for n, c in enumerate(chunks, 1):
        meta = [SOURCE_TYPES.get(c.source, c.source), f"Link: {c.link}"]
        if c.updated_at:
            meta.append(f"Updated: {c.updated_at:%Y-%m-%d}")
        if c.status:
            meta.append(f"Design doc status: {c.status}")
        blocks.append(f"[{n}] {c.heading_path}\n{' | '.join(meta)}\n{c.content}")
    return "\n\n---\n\n".join(blocks)


def generate_answer(question: str, chunks: list[Candidate], on_text: Callable[[str], None] | None = None) -> Answer:
    """Write the answer. With on_text, the answer is streamed: on_text gets each new piece as it arrives."""
    if not chunks:
        if on_text:
            on_text(NOT_FOUND)
        return Answer(NOT_FOUND, [], [], 0, 0)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Sources:\n\n{format_sources(chunks)}\n\nQuestion: {question}"},
    ]
    if on_text is None:
        response = get_client().chat.completions.create(name="gpt-answer", model=LLM_MODEL, temperature=0,
                                                        messages=messages)
        text, usage = response.choices[0].message.content.strip(), response.usage
    else:
        stream = get_client().chat.completions.create(name="gpt-answer", model=LLM_MODEL, temperature=0,
                                                      messages=messages, stream=True,
                                                      stream_options={"include_usage": True})
        parts, usage = [], None
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                parts.append(chunk.choices[0].delta.content)
                on_text(chunk.choices[0].delta.content)
            if getattr(chunk, "usage", None):
                usage = chunk.usage  # sent with the last chunk
        text = "".join(parts).strip()
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text) if 1 <= int(n) <= len(chunks)})
    return Answer(text, chunks, cited, usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0)
