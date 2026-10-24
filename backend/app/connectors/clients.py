"""Thin Slack and GitLab API clients: check a token and list the channels or projects it can see.

Step 9 adds fetching content (messages, issues, wiki pages) on top of these.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

TIMEOUT = 20


class ConnectorError(Exception):
    """A message an admin can act on, such as 'Slack says: invalid_auth'."""


@dataclass
class Container:
    id: str
    name: str
    kind: str   # public_channel, private_channel, project


def _get(url: str, headers: dict) -> tuple[object, dict]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read() or b"null"), dict(r.headers)
    except urllib.error.HTTPError as e:
        raise ConnectorError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}") from None
    except urllib.error.URLError as e:
        raise ConnectorError(f"Can't reach {urllib.parse.urlsplit(url).netloc}: {e.reason}") from None


class Slack:
    API = "https://slack.com/api/"

    def __init__(self, token: str):
        self.headers = {"Authorization": f"Bearer {token}"}

    def call(self, method: str, **params) -> dict:
        query = urllib.parse.urlencode(params)
        data, _ = _get(f"{self.API}{method}?{query}", self.headers)
        if not data.get("ok"):
            needed = f" (missing scope: {data['needed']})" if data.get("needed") else ""
            raise ConnectorError(f"Slack says: {data.get('error')}{needed}")
        return data

    def check(self) -> dict:
        """Who the token belongs to; raises ConnectorError when it doesn't work."""
        info = self.call("auth.test")
        return {"team": info.get("team"), "team_url": info.get("url"), "bot_user": info.get("user")}

    def containers(self) -> list[Container]:
        """Channels the bot is a member of: private channels only show up once it's invited."""
        found, cursor = [], ""
        while True:
            data = self.call("conversations.list", types="public_channel,private_channel",
                             exclude_archived="true", limit=200, cursor=cursor)
            for c in data["channels"]:
                if c.get("is_member"):
                    found.append(Container(c["id"], f"#{c['name']}", "private_channel" if c["is_private"] else "public_channel"))
            cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                return sorted(found, key=lambda c: c.name)


class GitLab:
    def __init__(self, url: str, token: str, group: str):
        self.base = f"{url.rstrip('/')}/api/v4"
        self.headers = {"PRIVATE-TOKEN": token}
        self.group = group

    def get(self, path: str) -> tuple[object, dict]:
        return _get(self.base + path, self.headers)

    def check(self) -> dict:
        user, _ = self.get("/user")
        group, _ = self.get(f"/groups/{urllib.parse.quote(self.group, safe='')}")
        return {"user": user.get("username"), "group": group.get("full_path"), "group_name": group.get("name"),
                "group_url": group.get("web_url")}

    def containers(self) -> list[Container]:
        found, page = [], "1"
        group = urllib.parse.quote(self.group, safe="")
        while page:
            projects, headers = self.get(f"/groups/{group}/projects?include_subgroups=true&per_page=100&page={page}")
            found += [Container(str(p["id"]), p["path_with_namespace"].split("/", 1)[-1], "project") for p in projects]
            page = headers.get("X-Next-Page") or headers.get("x-next-page") or ""
        return sorted(found, key=lambda c: c.name)


def client(kind: str, token: str, config: dict) -> Slack | GitLab:
    if kind == "slack":
        return Slack(token)
    if kind == "gitlab":
        if not config.get("url") or not config.get("group"):
            raise ConnectorError("GitLab needs the instance URL and the group path")
        return GitLab(config["url"], token, config["group"])
    raise ConnectorError(f"Unknown connector type: {kind}")
