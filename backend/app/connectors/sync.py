"""Sync connectors into the search index, on a schedule, on demand, or from the command line.

One run fetches every channel or project the connector found, stores new and changed
documents (unchanged ones are skipped by content hash), and deletes documents that are
gone from the tool. Each run is recorded in sync_runs.

The scheduler is a small background thread in the API: every minute it syncs the enabled
connectors whose interval has passed. Turn it off with SYNC_SCHEDULER=0 in .env.

Usage (from the project root):
    python -m app.connectors.sync              # every enabled connector
    python -m app.connectors.sync --name Slack # connectors whose name contains "Slack"
"""

import argparse
import logging
import threading
import time
import zlib

from app.connectors.clients import ConnectorError, client
from app.connectors.fetch import gitlab_project, slack_threads
from app.db.connection import connect
from app.ingestion.store import ADMINS_ONLY, sync_documents
from app.vault import decrypt

log = logging.getLogger("gitmore.sync")


def _names(conn) -> dict[str, str]:
    """Slack handles and GitLab usernames → display names, for authors in hidden notes."""
    rows = conn.execute("SELECT slack_handle, gitlab_username, name FROM users").fetchall()
    return {h: name for slack, gitlab, name in rows for h in (slack, gitlab) if h}


def run_sync(connector_id: str, trigger: str = "manual", container_id: str | None = None) -> dict:
    """Sync one connector, or only one of its channels or projects (container_id, used by events).

    Returns the run's counts, or {'skipped': reason}. A full sync skips when another is running;
    an event sync waits for it, so a change that arrives mid-sync is never lost.
    """
    with connect() as conn:
        conn.autocommit = True  # the run row and the lock are visible immediately
        lock = zlib.crc32(connector_id.encode())
        if container_id:
            conn.execute("SELECT pg_advisory_lock(%s)", (lock,))
        elif not conn.execute("SELECT pg_try_advisory_lock(%s)", (lock,)).fetchone()[0]:
            return {"skipped": "already syncing"}
        try:
            row = conn.execute("SELECT kind, name, config, token_encrypted, enabled FROM connectors WHERE id = %s",
                               (connector_id,)).fetchone()
            if not row:
                return {"skipped": "no such connector"}
            kind, name, config, token, enabled = row
            if not enabled and trigger != "manual":
                return {"skipped": "turned off"}
            run_id = conn.execute("INSERT INTO sync_runs (connector_id, trigger) VALUES (%s, %s) RETURNING id",
                                  (connector_id, trigger)).fetchone()[0]
            try:
                stats = _sync(conn, connector_id, kind, config, decrypt(token), container_id)
            except (ConnectorError, RuntimeError, KeyError) as e:
                conn.execute("UPDATE sync_runs SET status = 'error', error = %s, finished_at = now() WHERE id = %s",
                             (str(e), run_id))
                conn.execute("UPDATE connectors SET status = 'error', last_error = %s WHERE id = %s", (str(e), connector_id))
                log.warning("sync of %s failed: %s", name, e)
                return {"error": str(e)}
            conn.execute(
                "UPDATE sync_runs SET status = 'ok', finished_at = now(), seen = %s, changed = %s, deleted = %s, "
                "chunks = %s WHERE id = %s",
                (stats.seen, stats.changed, stats.deleted, stats.chunks, run_id),
            )
            if container_id:
                conn.execute("UPDATE connectors SET last_event_at = now() WHERE id = %s", (connector_id,))
            else:
                conn.execute("UPDATE connectors SET last_sync_at = now(), status = 'connected', last_error = NULL "
                             "WHERE id = %s", (connector_id,))
            log.info("synced %s: %s", name, stats)
            return stats.__dict__
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (lock,))


def _sync(conn, connector_id: str, kind: str, config: dict, token: str, only: str | None = None):
    api = client(kind, token, config)
    names = _names(conn)
    containers = conn.execute(
        "SELECT id::text, container_id, container_name, allowed_roles FROM source_access "
        "WHERE connector_id = %s AND (%s::text IS NULL OR container_id = %s)",
        (connector_id, only, only),
    ).fetchall()

    def docs():
        for access_id, container_id, container_name, roles in containers:
            roles = roles or [ADMINS_ONLY]
            if kind == "slack":
                yield from slack_threads(api, container_id, container_name, roles, access_id,
                                         config.get("team_url") or "https://slack.com", names)
            else:
                yield from gitlab_project(api, container_id, container_name, roles, access_id, names)

    access_ids = [c[0] for c in containers]
    with conn.transaction():
        return sync_documents(conn, docs(), "access_id = ANY(%s)", (access_ids,))


def due_connectors() -> list[str]:
    with connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT id::text FROM connectors WHERE enabled AND (last_sync_at IS NULL OR "
            "last_sync_at + make_interval(mins => sync_interval_minutes) <= now()) ORDER BY last_sync_at NULLS FIRST"
        )]


class Scheduler:
    """Every minute, sync the connectors that are due. One thread, one connector at a time."""

    def __init__(self, every_seconds: int = 60):
        self.every = every_seconds
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="gitmore-sync", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def _loop(self) -> None:
        while not self.stop_event.wait(self.every):
            try:
                for connector_id in due_connectors():
                    if self.stop_event.is_set():
                        return
                    run_sync(connector_id, "schedule")
            except Exception:  # keep the scheduler alive whatever one run does
                log.exception("scheduled sync failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", help="only connectors whose name contains this text")
    args = parser.parse_args()
    with connect() as conn:
        rows = conn.execute("SELECT id::text, name FROM connectors WHERE enabled ORDER BY created_at").fetchall()
    for connector_id, name in rows:
        if args.name and args.name.lower() not in name.lower():
            continue
        start = time.perf_counter()
        print(f"{name}: {run_sync(connector_id, 'script')} in {time.perf_counter() - start:.1f} s")


if __name__ == "__main__":
    main()
