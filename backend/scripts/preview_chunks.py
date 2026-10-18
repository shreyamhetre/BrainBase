"""Print the chunks for a few handbook pages, to review chunking before embedding.

Usage: python backend/scripts/preview_chunks.py total-rewards/benefits/_index.md [more paths...]
       (paths are relative to data/raw/handbook/content/handbook/)
"""

import sys

from app.ingestion.handbook import CONTENT, load_page

PREVIEW_CHARS = 500


def main(paths: list[str]) -> None:
    for rel in paths:
        page = load_page(CONTENT / rel)
        chunks = page.chunks()
        print("=" * 100)
        print(f"{page.rel_path}\n  title: {page.title}\n  url: {page.url}\n  section: {page.section}"
              f" | type: {page.doc_type} | status: {page.status} | updated: {page.updated_at}")
        print(f"  owners: {page.owners}\n  people: {sorted(page.people)}")
        print(f"  dropped shortcodes: {page.dropped_shortcodes}")
        print(f"  chunks: {len(chunks)}, tokens: {[c.token_count for c in chunks]}")
        for i, chunk in enumerate(chunks):
            text = chunk.content if len(chunk.content) <= PREVIEW_CHARS else chunk.content[:PREVIEW_CHARS] + " [...]"
            print(f"\n  --- chunk {i} | {chunk.token_count} tokens | #{chunk.anchor} | people {chunk.people}")
            print(f"  {chunk.heading_path}")
            print("  " + text.replace("\n", "\n  "))
    print()


if __name__ == "__main__":
    main(sys.argv[1:])
