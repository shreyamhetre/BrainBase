"""Refresh the handbook from the app: pull the latest pages, re-date them, re-index what changed.

Runs in a background thread in the API. Steps:
1. git pull in data/raw/handbook (the sparse, one-year clone)
2. backend/scripts/handbook_dates.py: each page's last-change date
3. ingest with the current RAG settings (sections kept, age window): unchanged pages are
   skipped, new or edited pages are embedded, pages no longer selected are removed

Its status is kept in app_settings under "handbook_job", for the admin page.
"""

import json
import logging
import subprocess
import sys
import threading
import zlib
from datetime import datetime, timezone

from app.config import DATA_DIR, PROJECT_ROOT
from app.db.connection import connect

log = logging.getLogger("gitmore.handbook")
KEY = "handbook_job"
REPO = DATA_DIR / "raw" / "handbook"
LOCK = zlib.crc32(b"handbook-refresh")


def _status(conn, **fields) -> None:
    current = conn.execute("SELECT value FROM app_settings WHERE key = %s", (KEY,)).fetchone()
    value = {**(current[0] if current else {}), **fields}
    conn.execute("INSERT INTO app_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET "
                 "value = EXCLUDED.value, updated_at = now()", (KEY, json.dumps(value)))


def status() -> dict:
    with connect() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = %s", (KEY,)).fetchone()
    return row[0] if row else {"state": "never"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(admin_id: str) -> None:
    from app.ingestion import handbook, ingest_handbook

    with connect() as conn:
        conn.autocommit = True
        if not conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK,)).fetchone()[0]:
            return
        try:
            _status(conn, state="running", step="Pulling the latest handbook from GitLab", started_at=_now(),
                    finished_at=None, error=None, stats=None, started_by=admin_id)
            pull = subprocess.run(["git", "-C", str(REPO), "pull", "--ff-only"], capture_output=True, text=True, timeout=900)
            if pull.returncode != 0:
                raise RuntimeError(f"git pull failed: {(pull.stderr or pull.stdout).strip()[:300]}")

            _status(conn, step="Dating each page from its Git history")
            dates = subprocess.run([sys.executable, str(PROJECT_ROOT / "backend" / "scripts" / "handbook_dates.py")],
                                   capture_output=True, text=True, timeout=900, cwd=str(PROJECT_ROOT))
            if dates.returncode != 0:
                raise RuntimeError(f"Dating pages failed: {(dates.stderr or dates.stdout).strip()[-300:]}")

            # The loader caches dates in memory: forget them so the new ones are used
            handbook._dates.cache_clear()
            handbook.snapshot_date.cache_clear()
            handbook.design_doc_status.cache_clear()

            _status(conn, step="Indexing new and changed pages")
            stats = ingest_handbook.run(log=lambda line: log.info(line))
            _status(conn, state="done", step=None, finished_at=_now(), stats=stats,
                    pulled=pull.stdout.strip().splitlines()[-1] if pull.stdout.strip() else "")
        except Exception as e:  # noqa: BLE001 - shown to the admin as is
            log.exception("handbook refresh failed")
            _status(conn, state="error", step=None, finished_at=_now(), error=str(e)[:500])
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK,))


def start(admin_id: str) -> bool:
    """Start a refresh in the background; False when one is already running."""
    if status().get("state") == "running":
        return False
    threading.Thread(target=_run, args=(admin_id,), name="handbook-refresh", daemon=True).start()
    return True
