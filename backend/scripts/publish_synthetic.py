"""Post the reviewed synthetic data to Slack and GitLab.

- Slack: each message is posted by the GitMore bot under the person's name, with the
  intended author and date in Slack message metadata (the API can't backdate messages).
- GitLab: issues (with comments, closed if needed) and wiki pages, each starting with a
  hidden note <!-- gitmore: author=..., date=... --> that the connector reads. Issue and
  comment dates are set through the API (allowed for the group owner).

Never posts twice: what was posted is recorded in data/raw/synthetic_published.json, and
existing GitLab issues and wiki pages with the same title are skipped.

Usage:
    python backend/scripts/publish_synthetic.py          # dry run: shows what would be posted
    python backend/scripts/publish_synthetic.py --yes    # actually post
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from app.config import DATA_DIR

SYNTHETIC = DATA_DIR / "synthetic"
STATE_FILE = DATA_DIR / "raw" / "synthetic_published.json"
SLACK_API = "https://slack.com/api/"


def load(name: str) -> dict:
    return json.loads((SYNTHETIC / name).read_text(encoding="utf-8"))


def hidden_note(author: str, date: str) -> str:
    return f"<!-- gitmore: author={author}, date={date} -->"


class Slack:
    def __init__(self, token: str):
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

    def call(self, method: str, **params) -> dict:
        body = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(SLACK_API + method, data=body, headers=self.headers)
        data = json.load(urllib.request.urlopen(req, timeout=30))
        if not data.get("ok"):
            raise RuntimeError(f"Slack {method} failed: {data.get('error')} {data.get('needed', '')}")
        return data

    def channel_ids(self) -> dict[str, str]:
        # Read methods ignore JSON bodies, so the parameters go in the URL
        query = urllib.parse.urlencode({"types": "public_channel,private_channel", "limit": 200})
        req = urllib.request.Request(f"{SLACK_API}conversations.list?{query}", headers=self.headers)
        data = json.load(urllib.request.urlopen(req, timeout=30))
        if not data.get("ok"):
            raise RuntimeError(f"Slack conversations.list failed: {data.get('error')}")
        return {c["name"]: c["id"] for c in data["channels"]}


class GitLab:
    def __init__(self, url: str, token: str, group: str):
        self.base = f"{url.rstrip('/')}/api/v4"
        self.headers = {"PRIVATE-TOKEN": token, "Content-Type": "application/json"}
        self.group = group

    def call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"GitLab {method} {path} failed: {e.code} {e.read().decode()[:300]}") from None

    def project_ids(self) -> dict[str, int]:
        group = urllib.parse.quote(self.group, safe="")
        return {p["path"]: p["id"] for p in self.call("GET", f"/groups/{group}/projects?per_page=100")}


def publish_slack(slack: Slack | None, people: dict, state: dict, dry_run: bool) -> None:
    data = load("slack.json")
    messages = sorted(data["messages"], key=lambda m: m["date"])  # parents before replies
    channels = slack.channel_ids() if slack else {}
    posted = state.setdefault("slack", {})

    missing = sorted({m["channel"] for m in messages} - set(channels)) if slack else []
    if missing:
        raise RuntimeError(f"Bot can't see these channels (invite it first): {missing}")

    for m in messages:
        if m["id"] in posted:
            continue
        where = f"#{m['channel']}" + (f" (reply to {m['reply_to']})" if m.get("reply_to") else "")
        print(f"  slack {m['id']:<3} {where:<34} {people[m['author']]:<18} {m['text'][:55]}…")
        if dry_run:
            continue
        params = {
            "channel": channels[m["channel"]],
            "text": m["text"],
            "username": people[m["author"]],
            "unfurl_links": False,
            "metadata": {"event_type": "gitmore_synthetic",
                         "event_payload": {"id": m["id"], "author": m["author"], "date": m["date"]}},
        }
        if m.get("reply_to"):
            params["thread_ts"] = posted[m["reply_to"]]
        posted[m["id"]] = slack.call("chat.postMessage", **params)["ts"]
        save(state)
        time.sleep(1.2)  # Slack allows about one message per second per channel


def publish_issues(gitlab: GitLab | None, people: dict, state: dict, dry_run: bool) -> None:
    data = load("gitlab_issues.json")
    projects = gitlab.project_ids() if gitlab else {}
    posted = state.setdefault("issues", {})

    for issue in data["issues"]:
        key = f"{issue['project']}::{issue['title']}"
        if key in posted:
            continue
        flag = " [confidential]" if issue["confidential"] else ""
        print(f"  issue {issue['project']:<12} {issue['title'][:60]}{flag} ({len(issue['comments'])} comments, {issue['state']})")
        if dry_run:
            continue
        pid = projects[issue["project"]]
        existing = gitlab.call("GET", f"/projects/{pid}/issues?search={urllib.parse.quote(issue['title'])}&in=title")
        if any(e["title"] == issue["title"] for e in existing):
            print("      already exists, skipped")
            posted[key] = "existing"
            continue
        assignees = ", ".join(people[h] for h in issue["assignees"])
        description = (f"{hidden_note(issue['author'], issue['created_at'])}\n\n{issue['description']}\n\n"
                       f"_Reported by {people[issue['author']]} · Assigned to {assignees}_")
        created = gitlab.call("POST", f"/projects/{pid}/issues", {
            "title": issue["title"], "description": description, "labels": ",".join(issue["labels"]),
            "confidential": issue["confidential"], "created_at": issue["created_at"],
        })
        for comment in issue["comments"]:
            gitlab.call("POST", f"/projects/{pid}/issues/{created['iid']}/notes", {
                "body": f"{hidden_note(comment['author'], comment['date'])}\n\n**{people[comment['author']]}:** {comment['body']}",
                "created_at": comment["date"],
            })
        if issue["state"] == "closed":
            gitlab.call("PUT", f"/projects/{pid}/issues/{created['iid']}", {"state_event": "close"})
        posted[key] = created["iid"]
        save(state)
        print(f"      created {issue['project']}#{created['iid']}")


def publish_wiki(gitlab: GitLab | None, people: dict, state: dict, dry_run: bool) -> None:
    data = load("gitlab_wiki.json")
    projects = gitlab.project_ids() if gitlab else {}
    posted = state.setdefault("wiki", {})

    for page in data["pages"]:
        key = f"{page['project']}::{page['title']}"
        if key in posted:
            continue
        print(f"  wiki  {page['project']:<12} {page['title'][:60]} (by {people[page['author']]})")
        if dry_run:
            continue
        pid = projects[page["project"]]
        existing = {p["title"] for p in gitlab.call("GET", f"/projects/{pid}/wikis")}
        if page["title"] in existing:
            print("      already exists, skipped")
            posted[key] = "existing"
            continue
        content = f"{hidden_note(page['author'], page['date'])}\n\n{page['content']}\n\n_Written by {people[page['author']]}_"
        created = gitlab.call("POST", f"/projects/{pid}/wikis", {"title": page["title"], "content": content, "format": "markdown"})
        posted[key] = created["slug"]
        save(state)


def save(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="actually post (default is a dry run)")
    args = parser.parse_args()
    dry_run = not args.yes

    people = {p["handle"]: p["name"] for p in load("people.json")["people"]}
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    slack = None if dry_run else Slack(os.environ["SLACK_BOT_TOKEN"])
    gitlab = None if dry_run else GitLab(os.environ["GITLAB_URL"], os.environ["GITLAB_TOKEN"], os.environ["GITLAB_GROUP"])

    print("DRY RUN, nothing is posted. Add --yes to post.\n" if dry_run else "Posting…\n")
    publish_slack(slack, people, state, dry_run)
    publish_issues(gitlab, people, state, dry_run)
    publish_wiki(gitlab, people, state, dry_run)
    if not dry_run:
        print(f"\nDone. Slack {len(state.get('slack', {}))}, issues {len(state.get('issues', {}))}, "
              f"wiki pages {len(state.get('wiki', {}))} recorded in {STATE_FILE.name}")


if __name__ == "__main__":
    main()
