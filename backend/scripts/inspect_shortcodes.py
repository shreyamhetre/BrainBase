"""List every Hugo shortcode used in the handbook, with counts and one example each.

Covers both {{< name ... >}} and {{% name ... %}}, skips code fences, and reports
whether each tag is a wrapper (has a closing {{< /name >}}) or stands alone.

Usage: python backend/scripts/inspect_shortcodes.py
"""

import re
from collections import Counter

from app.config import DATA_DIR

ROOT = DATA_DIR / "raw" / "handbook" / "content" / "handbook"
FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
SHORTCODE = re.compile(r"\{\{([<%])\s*(/?)\s*([\w./-]+)(.*?)\s*[>%]\}\}", re.DOTALL)


def main() -> None:
    opens, closes, files_with = Counter(), Counter(), Counter()
    in_fences = 0
    example: dict[str, str] = {}

    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        in_fences += sum(len(SHORTCODE.findall(m.group(0))) for m in FENCE.finditer(text))
        text = FENCE.sub("", text)

        seen = set()
        for match in SHORTCODE.finditer(text):
            _, slash, name, _ = match.groups()
            if slash:
                closes[name] += 1
            else:
                opens[name] += 1
                example.setdefault(name, " ".join(match.group(0).split())[:110])
            seen.add(name)
        files_with.update(seen)

    print(f"{len(opens)} distinct shortcodes ({sum(opens.values())} uses); "
          f"{in_fences} more inside code fences (left untouched)\n")
    print(f"{'name':<28}{'uses':>6}{'files':>7}  {'kind':<10} example")
    for name, count in opens.most_common():
        kind = "wrapper" if closes[name] else "single"
        print(f"{name:<28}{count:>6}{files_with[name]:>7}  {kind:<10} {example[name]}")


if __name__ == "__main__":
    main()
