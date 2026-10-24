"""Turn Slack threads and GitLab issues and wiki pages into SourceDocs for the index.

- Slack: one document per thread (the parent message plus its replies), so a reply like
  "yes, 20 days" keeps its question.
- GitLab: one document per issue (description plus comments) and per wiki page.
- Author and date come from the hidden notes and message metadata written by
  publish_synthetic.py, because everything was posted by one account on one day.
  Real content without them falls back to the API's author and dates.
"""

import re
import urllib.parse
from datetime import datetime, timezone

from app.connectors.clients import GitLab, Slack
from app.ingestion.store import SourceDoc

HIDDEN_NOTE = re.compile(r"<!--\s*gitmore:\s*author=([\w.\-]+),\s*date=([^\s>]+)\s*-->\s*")
SPOKEN_BY = re.compile(r"^\*\*[^*\n]{1,60}:\*\*\s*")          # "**Arjun Mehta:** " prefix on comments
SLACK_LINK = re.compile(r"<(https?://[^|>]+)(?:\|([^>]+))?>")
SLACK_MENTION = re.compile(r"<[@#!][^>]+>")
SKIP_SUBTYPES = {"channel_join", "channel_leave", "channel_topic", "channel_purpose", "channel_name",
                 "bot_add", "bot_remove", "channel_archive", "pinned_item"}


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return date if date.tzinfo else date.replace(tzinfo=timezone.utc)


def hidden_note(text: str) -> tuple[str | None, datetime | None, str]:
    """(author handle, date, text without the note)."""
    match = HIDDEN_NOTE.search(text or "")
    if not match:
        return None, None, text or ""
    return match.group(1), parse_date(match.group(2)), HIDDEN_NOTE.sub("", text, count=1).strip()


def slack_text(text: str) -> str:
    """Slack markup to plain Markdown: <url|label> → label (url), mentions dropped."""
    text = SLACK_LINK.sub(lambda m: f"{m.group(2)} ({m.group(1)})" if m.group(2) else m.group(1), text)
    return SLACK_MENTION.sub("", text).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()


def _day(date: datetime | None) -> str:
    return f"{date:%Y-%m-%d}" if date else "unknown date"


# ---------- Slack ----------

def _slack_message(m: dict, names: dict[str, str]) -> tuple[str, datetime, str]:
    payload = (m.get("metadata") or {}).get("event_payload") or {}
    handle = payload.get("author")
    author = names.get(handle, handle) if handle else (m.get("username") or m.get("user") or "someone")
    date = parse_date(payload.get("date")) or datetime.fromtimestamp(float(m["ts"]), tz=timezone.utc)
    return author, date, slack_text(m.get("text", ""))


def slack_threads(api: Slack, channel_id: str, channel_name: str, roles: list[str], access_id: str,
                  team_url: str, names: dict[str, str]) -> list[SourceDoc]:
    docs, cursor = [], ""
    while True:
        page = api.call("conversations.history", channel=channel_id, limit=200,
                        include_all_metadata="true", cursor=cursor)
        for parent in page["messages"]:
            if parent.get("subtype") in SKIP_SUBTYPES or parent.get("thread_ts", parent["ts"]) != parent["ts"]:
                continue  # system messages, and replies that were also sent to the channel
            messages = [parent]
            if parent.get("reply_count"):
                replies = api.call("conversations.replies", channel=channel_id, ts=parent["ts"],
                                   limit=200, include_all_metadata="true")["messages"]
                messages += [r for r in replies if r["ts"] != parent["ts"] and r.get("subtype") not in SKIP_SUBTYPES]

            said = [_slack_message(m, names) for m in messages]
            said = [(a, d, t) for a, d, t in said if t]
            if not said:
                continue
            first = said[0][2].splitlines()[0]
            title = f"{channel_name}: {first[:80]}{'…' if len(first) > 80 else ''}"
            body = "\n\n".join(f"**{a}** ({_day(d)}): {t}" for a, d, t in said)
            docs.append(SourceDoc(
                source="slack",
                external_id=f"{channel_id}:{parent['ts']}",
                title=title,
                url=f"{team_url.rstrip('/')}/archives/{channel_id}/p{parent['ts'].replace('.', '')}",
                body=body,
                allowed_roles=roles,
                updated_at=max(d for _, d, _ in said),
                section=channel_name,
                doc_type="thread",
                owners=[said[0][0]],
                people=sorted({a for a, _, _ in said}),
                metadata={"channel": channel_name, "replies": len(said) - 1},
                access_id=access_id,
            ))
        cursor = page.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            return docs


# ---------- GitLab ----------

def _pages(api: GitLab, path: str) -> list[dict]:
    items, page = [], "1"
    sep = "&" if "?" in path else "?"
    while page:
        batch, headers = api.get(f"{path}{sep}per_page=100&page={page}")
        items += batch
        page = headers.get("X-Next-Page") or headers.get("x-next-page") or ""
    return items


def gitlab_project(api: GitLab, project_id: str, project_name: str, roles: list[str], access_id: str,
                   names: dict[str, str]) -> list[SourceDoc]:
    project, _ = api.get(f"/projects/{project_id}")
    docs = []

    for issue in _pages(api, f"/projects/{project_id}/issues?scope=all&state=all"):
        handle, created, description = hidden_note(issue.get("description") or "")
        author = names.get(handle, handle) if handle else issue["author"]["name"]
        created = created or parse_date(issue["created_at"])
        people, dates, comments = {author}, [created], []
        for note in _pages(api, f"/projects/{project_id}/issues/{issue['iid']}/notes?sort=asc"):
            if note.get("system"):
                continue
            n_handle, n_date, text = hidden_note(note["body"])
            who = names.get(n_handle, n_handle) if n_handle else note["author"]["name"]
            when = n_date or parse_date(note["created_at"])
            people.add(who)
            dates.append(when)
            comments.append(f"**{who}** ({_day(when)}): {SPOKEN_BY.sub('', text)}")

        state = "closed" if issue["state"] == "closed" else "open"
        flags = ", ".join(filter(None, ["confidential" if issue.get("confidential") else "", state,
                                        f"labels: {', '.join(issue['labels'])}" if issue.get("labels") else ""]))
        body = f"Reported by {author} on {_day(created)} ({flags}).\n\n{description}"
        if comments:
            body += "\n\n## Comments\n\n" + "\n\n".join(comments)
        docs.append(SourceDoc(
            source="gitlab_issue",
            external_id=f"{project_id}#{issue['iid']}",
            title=f"{project_name}#{issue['iid']}: {issue['title']}",
            url=issue["web_url"],
            body=body,
            allowed_roles=roles,
            updated_at=max(d for d in dates if d),
            section=project_name,
            doc_type="issue",
            owners=[author],
            people=sorted(people),
            metadata={"project": project_name, "iid": issue["iid"], "state": state,
                      "confidential": bool(issue.get("confidential")), "labels": issue.get("labels", [])},
            access_id=access_id,
        ))

    for page in _pages(api, f"/projects/{project_id}/wikis?with_content=1"):
        handle, date, content = hidden_note(page.get("content") or "")
        author = names.get(handle, handle) if handle else None
        docs.append(SourceDoc(
            source="gitlab_wiki",
            external_id=f"{project_id}/wiki/{page['slug']}",
            title=page["title"],
            url=f"{project['web_url']}/-/wikis/{urllib.parse.quote(page['slug'])}",
            body=content,
            allowed_roles=roles,
            updated_at=date,
            section=project_name,
            doc_type="wiki",
            owners=[author] if author else [],
            people=[author] if author else [],
            metadata={"project": project_name, "slug": page["slug"]},
            access_id=access_id,
        ))
    return docs
