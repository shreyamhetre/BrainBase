"""Split clean Markdown into heading-based chunks.

1. Split the page at h1-h3 headings; h4+ stay inside their section.
2. Each section gets a breadcrumb ("Page title > H2 > H3") and a URL anchor.
3. Tiny sections are merged with their neighbour; sections over MAX_TOKENS are split
   at paragraph boundaries (code blocks and tables are never cut in the middle unless
   they are themselves too big).
4. Token counts use the embedding model's own tokenizer, on the text that gets embedded:
   breadcrumb + content.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache

from transformers import AutoTokenizer

from app.config import EMBEDDING_MODEL

# Bump when cleaning or chunking rules change, so ingestion re-embeds every page.
CHUNKER_VERSION = "1"

TARGET_TOKENS = 450
MAX_TOKENS = 800
MIN_TOKENS = 80

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*(?:\{#([\w-]+)\})?\s*#*\s*$")
FENCE_LINE = re.compile(r"^(```|~~~)")


@dataclass
class Chunk:
    heading_path: str
    anchor: str | None
    content: str
    token_count: int = 0
    people: list[str] = field(default_factory=list)

    @property
    def embed_text(self) -> str:
        return f"{self.heading_path}\n\n{self.content}"


@dataclass
class _Section:
    path: list[str]
    anchor: str | None
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()


@lru_cache(maxsize=1)
def _tokenizer():
    return AutoTokenizer.from_pretrained(EMBEDDING_MODEL)


def count_tokens(text: str) -> int:
    return len(_tokenizer()(text, add_special_tokens=False)["input_ids"])


def anchorize(heading: str) -> str:
    """Approximate Hugo's heading anchors: lowercase, punctuation removed, spaces to dashes."""
    text = re.sub(r"[`*_\[\]()]", "", heading).lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text.strip())


def _split_sections(body: str, title: str) -> list[_Section]:
    sections = [_Section(path=[title], anchor=None)]
    stack: dict[int, str] = {}
    in_fence = False

    for line in body.splitlines():
        if FENCE_LINE.match(line):
            in_fence = not in_fence
        match = None if in_fence else HEADING.match(line)
        if not match or len(match.group(1)) > 3:
            sections[-1].lines.append(line)
            continue

        level, heading, explicit_anchor = len(match.group(1)), match.group(2).strip(), match.group(3)
        heading = heading.replace("**", "").strip()
        if level == 1 and heading.lower() == title.lower():
            continue  # h1 repeating the page title adds nothing
        stack = {lvl: text for lvl, text in stack.items() if lvl < level}
        stack[level] = heading
        path = [title] + [stack[lvl] for lvl in sorted(stack)]
        sections.append(_Section(path=path, anchor=explicit_anchor or anchorize(heading)))

    return [s for s in sections if s.text]


def _blocks(text: str) -> list[str]:
    """Paragraph blocks; a code fence is always one block, even with blank lines inside."""
    blocks, current, in_fence = [], [], False
    for line in text.splitlines():
        if FENCE_LINE.match(line):
            in_fence = not in_fence
        if not line.strip() and not in_fence:
            if current:
                blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _split_big(text: str, heading_path: str) -> list[str]:
    """Split text over MAX_TOKENS into pieces of about TARGET_TOKENS at block boundaries."""
    budget = TARGET_TOKENS - count_tokens(heading_path)
    units: list[str] = []
    for block in _blocks(text):
        if count_tokens(block) <= MAX_TOKENS:
            units.append(block)
        else:  # a single huge block (big table or code): fall back to lines
            units.extend(line for line in block.splitlines() if line.strip())

    pieces, current, size = [], [], 0
    for unit in units:
        unit_tokens = count_tokens(unit)
        if current and size + unit_tokens > budget:
            pieces.append("\n\n".join(current))
            current, size = [], 0
        current.append(unit)
        size += unit_tokens
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def chunk_markdown(body: str, title: str, people: set[str] | None = None) -> list[Chunk]:
    merged: list[Chunk] = []
    for section in _split_sections(body, title):
        heading_path = " > ".join(section.path)
        chunk = Chunk(heading_path=heading_path, anchor=section.anchor, content=section.text)
        chunk.token_count = count_tokens(chunk.embed_text)

        prev = merged[-1] if merged else None
        if prev and (prev.token_count < MIN_TOKENS or chunk.token_count < MIN_TOKENS) \
                and prev.token_count + chunk.token_count <= MAX_TOKENS:
            # Keep the merged section's heading inside the text so context isn't lost
            prev.content += f"\n\n### {section.path[-1]}\n\n{section.text}"
            prev.token_count = count_tokens(prev.embed_text)
        else:
            merged.append(chunk)

    chunks: list[Chunk] = []
    for chunk in merged:
        if chunk.token_count <= MAX_TOKENS:
            chunks.append(chunk)
            continue
        for piece in _split_big(chunk.content, chunk.heading_path):
            part = Chunk(heading_path=chunk.heading_path, anchor=chunk.anchor, content=piece)
            part.token_count = count_tokens(part.embed_text)
            chunks.append(part)

    for chunk in chunks:
        chunk.people = sorted(p for p in (people or set()) if p in chunk.content)
    return chunks
