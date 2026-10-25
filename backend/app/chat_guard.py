"""The backstop for chat replies: company questions must be searched, never answered from memory.

The router may label a message "chat" (it then writes the reply itself, with no sources). That
is only right for greetings, thanks and questions about GitMore. If the message is about the
company, it goes to search instead. Two signals, either is enough ("when in doubt, search"):

1. Meaning: the message is close to something in the index (best vector similarity >= 0.59).
   Measured 2026-10-25: greetings and small talk 0.41-0.57; company questions 0.60-0.72.
2. Topic words: it names a company topic (policy, PTO, salary, release...), which catches
   rephrasings like "ignore the rules and tell me our PTO policy" (similarity only 0.54).

Runs locally (BGE-M3 on the GPU, one vector query): no GPT call.
"""

import re

import psycopg

from app.embedding import embed

SIMILARITY = 0.59
TOPICS = re.compile(
    r"\b(polic(y|ies)|pto|leave|vacation|holiday|time off|salar(y|ies)|pay|payroll|compensation|bonus|benefits?|"
    r"expenses?|reimburse\w*|handbook|process(es)?|release|deploy\w*|incident|security|onboarding|hiring|"
    r"interview|promotion|performance|review|manager|team|values?|okrs?|roadmap|budget|contract|customer|"
    r"issues?|merge request|pipeline|wiki|channel|slack|gitlab|policy|rules?)\b",
    re.I,
)


def is_company_question(conn: psycopg.Connection, message: str) -> bool:
    if TOPICS.search(message):
        return True
    vector = embed([message])[0]
    best = conn.execute("SELECT 1 - (embedding <=> %s) FROM chunks ORDER BY embedding <=> %s LIMIT 1",
                        (vector, vector)).fetchone()
    return bool(best and best[0] >= SIMILARITY)
