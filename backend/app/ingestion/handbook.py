"""Read one handbook page: front matter, metadata, clean text and chunks."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import frontmatter

from app.config import DATA_DIR
from app.ingestion.chunker import Chunk, chunk_markdown
from app.ingestion.handbook_selection import DESIGN_DOCS_PREFIX, should_ingest
from app.ingestion.markdown_clean import clean_markdown

REPO = DATA_DIR / "raw" / "handbook"
CONTENT = REPO / "content" / "handbook"
INCLUDES = REPO / "assets"
DATES_FILE = DATA_DIR / "raw" / "handbook_dates.json"
BASE_URL = "https://handbook.gitlab.com/handbook/"
OWNER_KEYS = ("authors", "dris", "approvers", "coach", "coaches", "owners")


@dataclass
class HandbookPage:
    rel_path: str                     # relative to content/handbook/, e.g. "total-rewards/benefits/_index.md"
    title: str
    url: str
    section: str
    doc_type: str                     # page | design_doc
    status: str | None                # design doc status
    owners: list[str]
    updated_at: datetime | None
    description: str
    body: str                         # clean text
    people: set[str] = field(default_factory=set)
    dropped_shortcodes: dict[str, int] = field(default_factory=dict)

    def chunks(self) -> list[Chunk]:
        return chunk_markdown(self.body, self.title, self.people)


@lru_cache(maxsize=1)
def _dates() -> dict[str, str]:
    return json.loads(DATES_FILE.read_text(encoding="utf-8")) if DATES_FILE.exists() else {}


@lru_cache(maxsize=1)
def snapshot_date() -> datetime:
    """Date of the newest change in our clone; the selection rules count back from it."""
    return max(datetime.fromisoformat(value) for value in _dates().values())


def last_changed(rel_path: str) -> datetime | None:
    value = _dates().get(f"content/handbook/{rel_path}")
    return datetime.fromisoformat(value) if value else None


def page_url(rel_path: str) -> str:
    path = rel_path.removesuffix(".md")
    path = path.removesuffix("_index").removesuffix("index").rstrip("/")
    return BASE_URL + (path + "/" if path else "")


@lru_cache(maxsize=None)
def design_doc_status(rel_path: str) -> str | None:
    """Status of the design document a page belongs to, read from the doc's index page."""
    if not rel_path.startswith(DESIGN_DOCS_PREFIX):
        return None
    parts = rel_path.removeprefix(DESIGN_DOCS_PREFIX).split("/")
    doc_dir = CONTENT / DESIGN_DOCS_PREFIX / parts[0]
    candidates = [doc_dir / "_index.md", doc_dir / "index.md"] if len(parts) > 1 else [CONTENT / rel_path]
    for candidate in candidates:
        if candidate.is_file():
            status = frontmatter.load(candidate).metadata.get("status")
            if status:
                return str(status).strip().lower()
    return None


def selected_pages() -> list[Path]:
    """All handbook pages that pass the selection rules (from the RAG settings), in a stable order."""
    from datetime import timedelta

    from app import rag_settings
    settings = rag_settings.get()
    core, max_age = set(settings.handbook_core_sections), timedelta(days=settings.handbook_max_age_days)
    snapshot = snapshot_date()
    pages = []
    for path in sorted(CONTENT.rglob("*.md")):
        rel = path.relative_to(CONTENT).as_posix()
        if should_ingest(rel, last_changed(rel), design_doc_status(rel), snapshot, core, max_age):
            pages.append(path)
    return pages


def _owners(meta: dict) -> list[str]:
    owners: list[str] = []
    for key in OWNER_KEYS:
        value = meta.get(key)
        values = value if isinstance(value, list) else [value] if value else []
        for item in values:
            item = str(item).strip()
            if item and item not in owners:
                owners.append(item)
    return owners


def load_page(path: Path) -> HandbookPage:
    rel_path = path.relative_to(CONTENT).as_posix()
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        post = frontmatter.loads(raw)
        meta, body = post.metadata, post.content
    except Exception:  # broken YAML: treat the whole file as body
        meta, body = {}, raw

    cleaned = clean_markdown(body, INCLUDES)
    fallback_title = path.parent.name if path.stem in ("_index", "index") else path.stem
    title = str(meta.get("title") or fallback_title)
    is_design_doc = rel_path.startswith(DESIGN_DOCS_PREFIX)

    return HandbookPage(
        rel_path=rel_path,
        title=title.strip(),
        url=page_url(rel_path),
        section=rel_path.split("/", 1)[0] if "/" in rel_path else "",
        doc_type="design_doc" if is_design_doc else "page",
        status=design_doc_status(rel_path),
        owners=_owners(meta),
        updated_at=last_changed(rel_path),
        description=str(meta.get("description") or "").strip(),
        body=cleaned.text,
        people=cleaned.people,
        dropped_shortcodes=dict(cleaned.dropped),
    )
