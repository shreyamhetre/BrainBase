"""Near-real-time updates: re-index a channel or project seconds after it changes.

- Slack, through Socket Mode: GitMore opens a WebSocket to Slack with the app-level token
  (xapp-…), so no public URL is needed. Each message event is acknowledged, and the channel
  is re-synced a few seconds later.
- GitLab, through webhooks (see api/hooks_routes.py): GitLab calls GitMore when an issue,
  comment or wiki page changes. That needs a public URL, e.g. a tunnel to the API.

Changes are debounced: a burst of events for one channel becomes one re-sync. The
scheduled sync still runs as a safety net for anything missed.
"""

import json
import logging
import threading
import urllib.request

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect as ws_connect

from app.connectors.sync import run_sync
from app.db.connection import connect
from app.vault import decrypt

log = logging.getLogger("gitmore.events")
DEBOUNCE_SECONDS = 3.0


class Debouncer:
    """Run fn(key) once, DEBOUNCE_SECONDS after the last call for that key."""

    def __init__(self, fn, delay: float = DEBOUNCE_SECONDS):
        self.fn, self.delay = fn, delay
        self.timers: dict[tuple, threading.Timer] = {}
        self.lock = threading.Lock()

    def __call__(self, *key) -> None:
        with self.lock:
            if key in self.timers:
                self.timers[key].cancel()
            timer = threading.Timer(self.delay, self._fire, key)
            timer.daemon = True
            self.timers[key] = timer
            timer.start()

    def _fire(self, *key) -> None:
        with self.lock:
            self.timers.pop(key, None)
        try:
            self.fn(*key)
        except Exception:
            log.exception("event sync failed for %s", key)


def resync_container(connector_id: str, container_id: str) -> None:
    result = run_sync(connector_id, "event", container_id)
    log.info("event sync %s/%s: %s", connector_id, container_id, result)


schedule_resync = Debouncer(resync_container)


def _set_status(connector_id: str, status: str, error: str | None = None) -> None:
    with connect() as conn:
        conn.execute("UPDATE connectors SET events_status = %s, events_error = %s WHERE id = %s",
                     (status, error, connector_id))


def open_socket_url(app_token: str) -> str:
    """Ask Slack for a Socket Mode WebSocket URL. Raises RuntimeError with Slack's reason."""
    req = urllib.request.Request("https://slack.com/api/apps.connections.open", data=b"", method="POST",
                                 headers={"Authorization": f"Bearer {app_token}",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    data = json.load(urllib.request.urlopen(req, timeout=20))
    if not data.get("ok"):
        raise RuntimeError(f"Slack says: {data.get('error')}")
    return data["url"]


class SlackSocket:
    """One Socket Mode connection for one Slack connector, in its own thread, reconnecting as needed."""

    def __init__(self, connector_id: str, app_token: str):
        self.connector_id, self.app_token = connector_id, app_token
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"slack-events-{connector_id[:8]}", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def _run(self) -> None:
        backoff = 2
        while not self.stop_event.is_set():
            try:
                with ws_connect(open_socket_url(self.app_token), open_timeout=20) as ws:
                    backoff = 2
                    self._listen(ws)
            except (RuntimeError, OSError, ConnectionClosed) as e:
                _set_status(self.connector_id, "error", str(e))
                log.warning("Slack events for %s: %s; retrying in %s s", self.connector_id, e, backoff)
                if self.stop_event.wait(backoff):
                    return
                backoff = min(backoff * 2, 300)

    def _listen(self, ws) -> None:
        while not self.stop_event.is_set():
            try:
                raw = ws.recv(timeout=1)
            except TimeoutError:
                continue
            envelope = json.loads(raw)
            kind = envelope.get("type")
            if envelope.get("envelope_id"):
                ws.send(json.dumps({"envelope_id": envelope["envelope_id"]}))  # Slack resends unacknowledged events
            if kind == "hello":
                _set_status(self.connector_id, "listening")
            elif kind == "disconnect":
                return  # Slack is rotating the connection; reconnect
            elif kind == "events_api":
                event = envelope.get("payload", {}).get("event", {})
                if event.get("type") == "message" and event.get("channel"):
                    schedule_resync(self.connector_id, event["channel"])


class EventManager:
    """Keeps one Socket Mode connection per Slack connector that has an app-level token."""

    def __init__(self):
        self.sockets: dict[str, SlackSocket] = {}
        self.lock = threading.Lock()

    def reload(self) -> None:
        with connect() as conn:
            rows = conn.execute(
                "SELECT id::text, events_secret_encrypted FROM connectors "
                "WHERE kind = 'slack' AND enabled AND events_secret_encrypted IS NOT NULL"
            ).fetchall()
        wanted = {}
        for connector_id, secret in rows:
            try:
                wanted[connector_id] = decrypt(secret)
            except RuntimeError as e:
                _set_status(connector_id, "error", str(e))
        with self.lock:
            for connector_id in list(self.sockets):
                if self.sockets[connector_id].app_token != wanted.get(connector_id):
                    self.sockets.pop(connector_id).stop()
            for connector_id, token in wanted.items():
                if connector_id not in self.sockets:
                    self.sockets[connector_id] = SlackSocket(connector_id, token)
                    self.sockets[connector_id].start()

    def stop(self) -> None:
        with self.lock:
            for socket in self.sockets.values():
                socket.stop()
            self.sockets.clear()


events = EventManager()
