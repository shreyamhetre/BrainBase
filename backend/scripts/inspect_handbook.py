"""Summarise the cloned handbook: pages, size, sections, front matter and headings.

Usage: python backend/scripts/inspect_handbook.py
"""

import re
import statistics
from collections import Counter

from app.config import DATA_DIR

ROOT = DATA_DIR / "raw" / "handbook" / "content" / "handbook"
FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING = re.compile(r"^(#{1,6})\s+\S", re.MULTILINE)
CHARS_PER_TOKEN = 4  # rough estimate for English text


def main() -> None:
    files = [p for p in ROOT.rglob("*") if p.is_file()]
    md_files = [p for p in files if p.suffix == ".md"]
    other_types = Counter(p.suffix or "(none)" for p in files if p.suffix != ".md")

    sections = Counter()
    section_tokens = Counter()
    fm_keys = Counter()
    heading_levels = Counter()
    page_tokens = []
    no_front_matter = 0
    no_headings = 0

    for path in md_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        section = path.relative_to(ROOT).parts[0] if len(path.relative_to(ROOT).parts) > 1 else "(root)"

        match = FRONT_MATTER.match(text)
        if match:
            for line in match.group(1).splitlines():
                key = re.match(r"^([A-Za-z_][\w-]*):", line)
                if key:
                    fm_keys[key.group(1)] += 1
            body = text[match.end():]
        else:
            no_front_matter += 1
            body = text

        levels = [len(h) for h in HEADING.findall(body)]
        heading_levels.update(levels)
        if not levels:
            no_headings += 1

        tokens = len(body) // CHARS_PER_TOKEN
        page_tokens.append(tokens)
        sections[section] += 1
        section_tokens[section] += tokens

    total = sum(page_tokens)
    print(f"Files: {len(files)}  (markdown: {len(md_files)})")
    print(f"Other file types: {dict(other_types.most_common(8))}")
    print(f"Total size: {sum(p.stat().st_size for p in md_files) / 1e6:.1f} MB of markdown")
    print(f"Estimated tokens: {total:,}  (~{total / 1e6:.1f}M)")
    print(
        f"Tokens per page: median {statistics.median(page_tokens):,.0f}, "
        f"p90 {sorted(page_tokens)[int(len(page_tokens) * 0.9)]:,}, max {max(page_tokens):,}"
    )
    print(f"Pages without front matter: {no_front_matter}, without headings: {no_headings}")

    print("\nHeading levels:", {f"h{k}": v for k, v in sorted(heading_levels.items())})

    print("\nFront matter keys (pages using each):")
    for key, count in fm_keys.most_common(15):
        print(f"  {key:<20} {count}")

    print("\nSections (pages, est. tokens):")
    for section, count in sections.most_common():
        print(f"  {section:<30} {count:>5}  {section_tokens[section]:>10,}")


if __name__ == "__main__":
    main()
