"""Which handbook pages get ingested.

Rules (option B, agreed 2026-10-05):
1. Pages changed in the last year are kept.
2. Core policy sections are kept whatever their age.
3. Design documents: implemented / ongoing / accepted / rejected are kept whatever
   their age; proposals untouched for over a year are dropped.

"The last year" is measured back from the snapshot date (the newest change in our
clone), not from today, so the same clone always selects the same pages.
"""

from datetime import datetime, timedelta

MAX_AGE = timedelta(days=365)

CORE_SECTIONS = {
    "values", "company", "people-policies", "total-rewards",
    "people-group", "hiring", "communication", "leadership",
}

DESIGN_DOCS_PREFIX = "engineering/architecture/design-documents/"
DESIGN_DOC_STATUSES_ALWAYS_KEPT = {"implemented", "ongoing", "accepted", "rejected"}


def should_ingest(
    rel_path: str, last_changed: datetime | None, design_status: str | None, snapshot: datetime
) -> bool:
    """rel_path is relative to content/handbook/, e.g. "total-rewards/benefits/_index.md".

    last_changed is None when the page has no commit in the fetched history (older than a year).
    design_status is the status of the design document the page belongs to, if any.
    snapshot is the date of the newest change in the clone.
    """
    recent = last_changed is not None and snapshot - last_changed <= MAX_AGE

    if rel_path.startswith(DESIGN_DOCS_PREFIX):
        return recent or (design_status or "").lower() in DESIGN_DOC_STATUSES_ALWAYS_KEPT

    section = rel_path.split("/", 1)[0] if "/" in rel_path else ""
    return recent or section in CORE_SECTIONS
