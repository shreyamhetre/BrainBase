"""Find each handbook page's last-change date from Git history.

The clone only has recent history (git fetch --shallow-since=...), so pages
with no commit in that window get no date: they are older than the window.

Writes data/raw/handbook_dates.json  {"content/handbook/...md": "2026-09-30T12:00:00+00:00"}
and prints how many pages fall in each age bucket, per section.

Usage: python backend/scripts/handbook_dates.py
"""

import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATA_DIR
from app.ingestion.handbook_selection import CORE_SECTIONS

DATA = DATA_DIR / "raw"
REPO = DATA / "handbook"
CONTENT = "content/handbook/"
OUT = DATA / "handbook_dates.json"


def last_change_dates() -> dict[str, str]:
    # The oldest fetched commits have no parent in a shallow clone, so Git
    # reports every file as "changed" there. Skip them to avoid fake dates.
    shallow_file = REPO / ".git" / "shallow"
    boundary = set(shallow_file.read_text().split()) if shallow_file.exists() else set()

    log = subprocess.run(
        ["git", "-C", str(REPO), "log", "--no-renames", "--name-only",
         "--format=@@%H %cI", "--", CONTENT],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout

    dates: dict[str, str] = {}
    skip = False
    commit_date = ""
    for line in log.splitlines():
        if line.startswith("@@"):
            sha, commit_date = line[2:].split(" ", 1)
            skip = sha in boundary
        elif line and not skip and line.endswith(".md"):
            dates.setdefault(line, commit_date)  # newest commit comes first
    return dates


def main() -> None:
    dates = last_change_dates()
    OUT.write_text(json.dumps(dates, indent=0, sort_keys=True), encoding="utf-8")

    now = datetime.now(timezone.utc)
    buckets = ["< 3 months", "3-6 months", "6-12 months", "> 12 months (no commit)"]
    per_section: dict[str, Counter] = defaultdict(Counter)

    for path in (REPO / CONTENT).rglob("*.md"):
        rel = path.relative_to(REPO).as_posix()
        parts = Path(rel).relative_to(CONTENT).parts
        section = parts[0] if len(parts) > 1 else "(root)"
        if rel in dates:
            age_days = (now - datetime.fromisoformat(dates[rel])).days
            bucket = buckets[0] if age_days < 91 else buckets[1] if age_days < 182 else buckets[2]
        else:
            bucket = buckets[3]
        per_section[section][bucket] += 1

    totals = Counter()
    for counts in per_section.values():
        totals.update(counts)

    print(f"Pages with a change in the fetched window: {len(dates)}")
    print(f"Wrote {OUT}\n")
    print(f"{'section':<30}" + "".join(f"{b:>14}" for b in ["<3m", "3-6m", "6-12m", ">12m"]) + "   core")
    for section in sorted(per_section, key=lambda s: -sum(per_section[s].values())):
        counts = per_section[section]
        core = "  yes" if section in CORE_SECTIONS else ""
        print(f"{section:<30}" + "".join(f"{counts[b]:>14}" for b in buckets) + core)
    print(f"{'TOTAL':<30}" + "".join(f"{totals[b]:>14}" for b in buckets))

    recent = totals[buckets[0]] + totals[buckets[1]] + totals[buckets[2]]
    core_old = sum(per_section[s][buckets[3]] for s in CORE_SECTIONS)
    print(f"\nKeep (changed in last 12 months + all core pages): {recent + core_old} of {sum(totals.values())}")


if __name__ == "__main__":
    main()
