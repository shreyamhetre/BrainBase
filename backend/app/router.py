"""The router: one model call that decides what a message needs.

- knowledge: a question, answered from the permission-filtered index (RAG)
- action:    something to do in a tool through MCP; GitMore drafts it and the person confirms
- clarify:   too vague to act on or search for; GitMore asks one short question

It only sees the actions this person may use and the projects they may act in, so it can't
propose anything they couldn't confirm.
"""

import json
from dataclasses import dataclass, field

from app.actions import Scope
from app.config import LLM_MODEL
from app.generation.answer import get_client

ROUTER_PROMPT = """You route messages for GitMore, a company assistant.

Decide what the message needs and reply with JSON only:
{"route": "knowledge" | "action" | "clarify",
 "question": "<for knowledge: the question to search for>",
 "clarify": "<for clarify: one short question back to the person>",
 "action": {"tool": "<tool name>", "summary": "<one line: what will happen, e.g. Create issue \\"X\\" in engineering>",
            "arguments": {<inputs for the tool, following its schema>},
            "context_query": "<only if the action needs facts from company knowledge first, else empty>"}}

Rules:
- "knowledge" for questions about policies, processes, people, decisions or anything to look up. This is the default.
- "action" only when the person clearly asks to do something one of the available tools does
  (create an issue, add a comment...). Never invent tools or projects.
- A message that asks to look something up AND do something with it ("summarize X and file it as an issue",
  "find Y and comment it on issue 4") is an "action", never "knowledge": set context_query to what to look up.
- Use project_id from the list of projects; never a project that isn't listed.
- To create an issue with save_work_item: project_id, type_name "Issue", a short title, and a clear description.
- To comment with save_note: project_id, work_item_iid (the issue number) and body.
- Write titles, descriptions and comments in plain, professional language. Don't add who asked; GitMore does.
- Use context_query ONLY when the person explicitly asks to include company information (summarize, look up,
  include the policy...). For "create an issue: <their text>", use their text as the description and no search.
- If the action needs facts from company knowledge ("summarize the PTO policy and file an issue"), put a search
  question in context_query and set the description or body to an empty string; it is written after the search.
- "clarify" when the message is too vague to search for or act on (e.g. "help", "do the thing"), or when an action
  is missing something you can't guess, such as which issue number.
- If the person asks for an action but no available tool does it, reply "clarify" saying plainly that this action
  isn't available to them in GitMore and that they can request access from their profile.
- If they name a project that isn't in the list, reply "clarify" naming the projects you can act in. Never ask for IDs.
"""


@dataclass
class Route:
    kind: str                     # knowledge, action, clarify
    question: str
    clarify: str = ""
    tool: str = ""
    summary: str = ""
    arguments: dict = field(default_factory=dict)
    context_query: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _tools_text(scope: Scope) -> str:
    lines = []
    for t in scope.tools:
        props = t.input_schema.get("properties", {})
        fields = "; ".join(f"{k} ({v.get('type', 'any')}): {(v.get('description') or '')[:100]}" for k, v in props.items())
        lines.append(f"- {t.name} ({t.server_name}): {t.description[:300]}\n  inputs: {fields}")
    return "\n".join(lines)


def route(message: str, scope: Scope) -> Route:
    # Runs even with no usable tools, so "create an issue" gets a clear reply instead of a search
    projects = "\n".join(f"- {p.name}: project_id {p.id}" for p in scope.projects) or "(none)"
    response = get_client().chat.completions.create(
        name="router",
        model=LLM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user", "content": f"Available tools:\n{_tools_text(scope) or '(none for this person)'}"
                                        f"\n\nProjects you may act in:\n{projects}"
                                        f"\n\nMessage: {message}"},
        ],
    )
    usage = response.usage
    try:
        data = json.loads(response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        data = {}
    kind = data.get("route") if data.get("route") in ("knowledge", "action", "clarify") else "knowledge"
    action = data.get("action") or {}
    result = Route(kind=kind, question=(data.get("question") or message).strip(), clarify=(data.get("clarify") or "").strip(),
                   tool=action.get("tool") or "", summary=(action.get("summary") or "").strip(),
                   arguments=action.get("arguments") if isinstance(action.get("arguments"), dict) else {},
                   context_query=(action.get("context_query") or "").strip(),
                   prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens)
    if result.kind == "action" and not scope.tool(result.tool):
        result.kind, result.question = "knowledge", message  # it picked a tool it can't use: just answer
    if result.kind == "clarify" and not result.clarify:
        result.kind, result.question = "knowledge", message
    return result


DRAFT_PROMPT = """You fill in an action for GitMore using company knowledge.
You get the action's current inputs and numbered sources. Rewrite only the text inputs (title, description, body)
so they contain the facts the person asked for, taken from the sources. Mention the source links you used at the end
of the description or body. Keep every other input unchanged. The summary says in one line what will happen,
not what happened, e.g. Create issue "Release checklist summary" in engineering.
Reply with JSON only: {"arguments": {...}, "summary": "..."}."""


def draft_with_context(message: str, route_: Route, sources_text: str) -> Route:
    response = get_client().chat.completions.create(
        name="draft-action",
        model=LLM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": DRAFT_PROMPT},
            {"role": "user", "content": f"Message: {message}\n\nCurrent inputs: {json.dumps(route_.arguments)}"
                                        f"\n\nSources:\n\n{sources_text}"},
        ],
    )
    usage = response.usage
    route_.prompt_tokens += usage.prompt_tokens
    route_.completion_tokens += usage.completion_tokens
    try:
        data = json.loads(response.choices[0].message.content or "{}")
        if isinstance(data.get("arguments"), dict):
            # Only text may change; ids and project stay as the router set them
            for key, value in data["arguments"].items():
                if isinstance(value, str) and key in ("title", "description", "body", "text"):
                    route_.arguments[key] = value
        route_.summary = (data.get("summary") or route_.summary).strip()
    except json.JSONDecodeError:
        pass
    return route_
