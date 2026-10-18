"""Chunk every selected handbook page (no embedding) and print totals.

Usage: python backend/scripts/chunk_stats.py
"""

import statistics
import time
from collections import Counter

from app.ingestion.handbook import CONTENT, design_doc_status, last_changed, load_page
from app.ingestion.handbook_selection import should_ingest


def main() -> None:
    start = time.perf_counter()
    paths = sorted(CONTENT.rglob("*.md"))
    selected = [
        p for p in paths
        if should_ingest(rel := p.relative_to(CONTENT).as_posix(), last_changed(rel), design_doc_status(rel))
    ]

    sizes: list[int] = []
    dropped, per_section = Counter(), Counter()
    empty_pages, pages_with_people = 0, 0
    for path in selected:
        page = load_page(path)
        chunks = page.chunks()
        if not chunks:
            empty_pages += 1
        pages_with_people += bool(page.people)
        dropped.update(page.dropped_shortcodes)
        per_section[page.section] += len(chunks)
        sizes.extend(c.token_count for c in chunks)

    sizes.sort()
    print(f"Pages: {len(selected)} selected of {len(paths)}  ({empty_pages} produced no chunks)")
    print(f"Chunks: {len(sizes)}  tokens: {sum(sizes):,}")
    print(f"Tokens per chunk: median {statistics.median(sizes):.0f}, p10 {sizes[len(sizes) // 10]}, "
          f"p90 {sizes[len(sizes) * 9 // 10]}, max {sizes[-1]}")
    print(f"Chunks under 50 tokens: {sum(s < 50 for s in sizes)}, over 800: {sum(s > 800 for s in sizes)}")
    print(f"Pages mentioning people: {pages_with_people}")
    print(f"Est. embedding time at ~22 chunks/s: {len(sizes) / 22 / 60:.0f} min")
    print(f"\nShortcodes removed without keeping text ({sum(dropped.values())} uses):")
    for name, count in dropped.most_common():
        print(f"  {name:<40} {count}")
    print("\nChunks per section (top 10):", dict(per_section.most_common(10)))
    print(f"\nTook {time.perf_counter() - start:.0f}s")


if __name__ == "__main__":
    main()
