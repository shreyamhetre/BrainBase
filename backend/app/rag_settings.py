"""RAG settings, managed by admins in the app (Admin console → Search & answers).

Search and answers read them on every message, so a change applies at once. They're cached
for a few seconds so busy chats don't query the database each time. The handbook rules apply
the next time the handbook is refreshed.
"""

import json
import time
from dataclasses import asdict, dataclass, field, fields

import psycopg

from app.config import LLM_MODEL, LLM_PRICE_INPUT_PER_M, LLM_PRICE_OUTPUT_PER_M
from app.db.connection import connect

KEY = "rag"
CACHE_SECONDS = 5

ANSWER_LENGTHS = {
    "short": "Be brief: two to four sentences, or up to four bullet points.",
    "normal": "Be concise: a short paragraph or a few bullet points.",
    "detailed": "Be thorough: explain step by step with headings or bullet points where useful, up to about 250 words.",
}

DEFAULT_CORE_SECTIONS = ["communication", "company", "hiring", "leadership", "people-group", "people-policies",
                         "total-rewards", "values"]


@dataclass
class RagSettings:
    # Search
    candidates_per_search: int = 50      # each of vector and keyword search returns this many
    rerank_pool: int = 30                # best fused results the reranker reads
    final_k: int = 5                     # sources passed to the model
    # Answers
    llm_model: str = LLM_MODEL
    price_input_per_m: float = LLM_PRICE_INPUT_PER_M
    price_output_per_m: float = LLM_PRICE_OUTPUT_PER_M
    answer_length: str = "normal"
    # Jev evidence gate (one retry with a rewritten question)
    gate_enabled: bool = True
    gate_threshold: float = 0.5          # Jev's "enough evidence" probability needed to answer
    gate_model: str = "jev-latest"
    gate_price_per_m: float = 0.042      # Jev charges input tokens only
    # Handbook (applied on the next refresh)
    handbook_core_sections: list[str] = field(default_factory=lambda: list(DEFAULT_CORE_SECTIONS))
    handbook_max_age_days: int = 365


# (min, max) for numbers; the handbook window can't exceed the one year of Git history in the clone
LIMITS = {"candidates_per_search": (10, 200), "rerank_pool": (5, 100), "final_k": (1, 10),
          "price_input_per_m": (0, 100), "price_output_per_m": (0, 400), "handbook_max_age_days": (30, 365),
          "gate_threshold": (0.1, 0.9), "gate_price_per_m": (0, 10)}
FLOATS = {"price_input_per_m", "price_output_per_m", "gate_threshold", "gate_price_per_m"}


NAMES = {"candidates_per_search": "Results per search", "rerank_pool": "Rerank pool", "final_k": "Sources per answer",
         "price_input_per_m": "Input price", "price_output_per_m": "Output price",
         "handbook_max_age_days": "Handbook age window (days)", "gate_threshold": "Evidence threshold",
         "gate_price_per_m": "Jev price"}


class SettingsError(ValueError):
    """A message the admin can act on."""


_cache: tuple[float, RagSettings] | None = None


def get() -> RagSettings:
    global _cache
    if _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
        return _cache[1]
    with connect() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = %s", (KEY,)).fetchone()
    stored = row[0] if row else {}
    known = {f.name for f in fields(RagSettings)}
    settings = RagSettings(**{k: v for k, v in stored.items() if k in known})
    _cache = (time.monotonic(), settings)
    return settings


def validate(changes: dict, available_sections: list[str]) -> dict:
    known = {f.name: f for f in fields(RagSettings)}
    clean = {}
    for key, value in changes.items():
        if key not in known:
            raise SettingsError(f"Unknown setting: {key}")
        if key in LIMITS:
            low, high = LIMITS[key]
            try:
                value = float(value) if key in FLOATS else int(value)
            except (TypeError, ValueError):
                raise SettingsError(f"{NAMES[key]} must be a number") from None
            if not low <= value <= high:
                raise SettingsError(f"{NAMES[key]} must be between {low} and {high}")
        elif key in ("llm_model", "gate_model"):
            value = str(value).strip()
            if not value or len(value) > 100:
                raise SettingsError("Enter a model name, e.g. gpt-4o-mini or jev-latest")
        elif key == "gate_enabled":
            if not isinstance(value, bool):
                raise SettingsError("The evidence gate is either on or off")
        elif key == "answer_length":
            if value not in ANSWER_LENGTHS:
                raise SettingsError("Answer length must be short, normal or detailed")
        elif key == "handbook_core_sections":
            value = sorted(set(value or []))
            unknown = set(value) - set(available_sections)
            if unknown:
                raise SettingsError(f"Not handbook sections: {sorted(unknown)}")
        clean[key] = value
    return clean


def save(conn: psycopg.Connection, changes: dict, admin_id: str) -> RagSettings:
    global _cache
    current = asdict(get())
    merged = {**current, **changes}
    if merged["rerank_pool"] < merged["final_k"]:
        raise SettingsError("The rerank pool must be at least the number of sources per answer")
    conn.execute(
        "INSERT INTO app_settings (key, value, updated_by, updated_at) VALUES (%s, %s, %s, now()) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, updated_at = now()",
        (KEY, json.dumps(merged), admin_id),
    )
    _cache = None
    return RagSettings(**merged)
