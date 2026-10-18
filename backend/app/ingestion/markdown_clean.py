"""Turn handbook Markdown (Hugo flavoured) into clean text for chunking.

- Inlines {{% include "..." %}} files.
- Replaces Hugo shortcodes with their useful text (see RULES below) and collects
  people mentioned in member/team shortcodes.
- Removes HTML comments and layout HTML tags, and turns links into their text.
- Never touches anything inside ``` / ~~~ code fences.
"""

import re
import shlex
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

FENCE = re.compile(r"^(```|~~~)[^\n]*\n.*?^\1[ \t]*$", re.MULTILINE | re.DOTALL)
ESCAPED_SHORTCODE = re.compile(r"\{\{[<%]/\*.*?\*/[>%]\}\}", re.DOTALL)
SHORTCODE = re.compile(r"\{\{([<%])\s*(/?)\s*([\w./-]+)(.*?)\s*/?\s*[>%]\}\}", re.DOTALL)
INCLUDE = re.compile(r"\{\{[<%]\s*include\s+\"([^\"]+)\"\s*[>%]\}\}")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
HTML_BLOCK_DROP = re.compile(r"<(style|script)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
HTML_TAG = re.compile(
    r"</?(?:div|span|details|summary|br|p|i|b|em|strong|sup|sub|a|iframe|center|font|u|hr|"
    r"ul|ol|li|table|thead|tbody|tr|td|th|img|small|code|kbd|figure|figcaption|section|"
    r"blockquote|h[1-6]|button|label|input|select|option|nav)\b[^>]*>",
    re.IGNORECASE,
)
IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
BLANK_LINES = re.compile(r"\n{3,}")

# Wrapper shortcodes: keep the inner text; the named attribute becomes a bold title line.
WRAPPER_TITLE_ATTR = {
    "alert": "title", "details": "summary", "panel": "header", "card": "header", "tab": "header",
    "note": None, "cardpane": None, "tabpane": None,
}
MAX_INCLUDE_DEPTH = 3


@dataclass
class CleanResult:
    text: str
    people: set[str] = field(default_factory=set)
    dropped: Counter = field(default_factory=Counter)  # shortcodes removed with no text kept


def _parse_args(raw: str) -> tuple[list[str], dict[str, str]]:
    """Split shortcode arguments into positional values and name="value" pairs."""
    try:
        tokens = shlex.split(raw.replace("\n", " "))
    except ValueError:
        tokens = raw.split()
    positional, named = [], {}
    for token in tokens:
        key, sep, value = token.partition("=")
        if sep and re.fullmatch(r"[\w-]+", key):
            named[key] = value
        else:
            positional.append(token)
    return positional, named


def _protect_fences(text: str) -> tuple[str, list[str]]:
    fences: list[str] = []

    def stash(match: re.Match) -> str:
        fences.append(match.group(0))
        return f"\x00FENCE{len(fences) - 1}\x00"

    return FENCE.sub(stash, text), fences


def _restore_fences(text: str, fences: list[str]) -> str:
    return re.sub(r"\x00FENCE(\d+)\x00", lambda m: fences[int(m.group(1))], text)


def _inline_includes(text: str, includes_root: Path, depth: int = 0) -> str:
    if depth >= MAX_INCLUDE_DEPTH:
        return text

    def replace(match: re.Match) -> str:
        path = includes_root / match.group(1)
        if not path.is_file():
            return ""
        included = path.read_text(encoding="utf-8", errors="replace")
        return _inline_includes(included, includes_root, depth + 1)

    return INCLUDE.sub(replace, text)


def _replace_shortcode(match: re.Match, result: CleanResult) -> str:
    _, closing, name, raw_args = match.groups()
    if closing:
        return ""  # closing tag of a wrapper: the inner text stays

    if name in WRAPPER_TITLE_ATTR:
        positional, named = _parse_args(raw_args)
        attr = WRAPPER_TITLE_ATTR[name]
        title = named.get(attr) if attr else None
        if name == "details" and not title and positional:
            title = positional[0]
        title = (title or "").replace("**", "").strip()
        return f"\n**{title}**\n" if title else ""

    positional, named = _parse_args(raw_args)

    if name == "member-by-name" and positional:
        result.people.update(positional)
        return ", ".join(positional)
    if name in {"member-by-gitlab", "member-and-role-by-gitlab", "group-by-slugs"} and positional:
        handles = [f"@{p.lstrip('@')}" for p in positional]
        result.people.update(handles)
        return ", ".join(handles)
    if name == "team-by-manager-slug" and (manager := named.get("manager") or (positional[0] if positional else "")):
        handle = f"@{manager.lstrip('@')}"
        result.people.add(handle)
        return f"(team of {handle})"
    if name == "engineering/stable-counterparts" and named.get("manager"):
        handle = f"@{named['manager'].lstrip('@')}"
        result.people.add(handle)
        return f"(stable counterparts of {handle})"
    if name == "manager-by-report-name" and positional:
        result.people.add(positional[0])
        return f"(manager of {positional[0]})"
    if name == "yes":
        return "Yes"
    if name == "no":
        return "No"
    if name == "label":
        return named.get("name") or (positional[0] if positional else "")
    if name in {"ref", "a"} and positional:
        return positional[0]
    if name in {"youtube", "vimeo"}:
        return "(video)"
    if name == "figure":
        return named.get("alt", "")

    result.dropped[name] += 1
    return ""


def clean_markdown(text: str, includes_root: Path) -> CleanResult:
    result = CleanResult(text="")

    # Includes first (outside code fences), then protect all fences, including included ones.
    protected, fences = _protect_fences(text)
    text = _restore_fences(_inline_includes(protected, includes_root), fences)
    text, fences = _protect_fences(text)

    text = ESCAPED_SHORTCODE.sub("", text)
    text = SHORTCODE.sub(lambda m: _replace_shortcode(m, result), text)
    text = HTML_COMMENT.sub("", text)
    text = HTML_BLOCK_DROP.sub("", text)
    text = HTML_TAG.sub("", text)
    text = IMAGE.sub(lambda m: m.group(1), text)
    text = LINK.sub(lambda m: m.group(1), text)
    text = BLANK_LINES.sub("\n\n", text)

    result.text = _restore_fences(text, fences).strip()
    return result
