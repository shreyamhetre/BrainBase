"""The question-answering graph. The router decides the path for every message:

    START → route ─┬─ knowledge → retrieve → answer ─────────────────→ END
                   ├─ action ───→ propose (search first if needed) ──→ END   (the person confirms later)
                   └─ clarify ─────────────────────────────────────────→ END

Each node is traced in Langfuse with @observe, nested under one trace per message, tagged
with the user who asked.
"""

import json
import re
from dataclasses import dataclass, field
from typing import TypedDict

from langfuse import get_client, observe, propagate_attributes
from langgraph.graph import END, START, StateGraph

from app.actions import ActionRefused, Scope, check, scope_for
from app.auth import User, search_roles
from app.db.connection import connect
from app.generation.answer import Answer, format_sources, generate_answer
from app.retrieval.retrieve import retrieve
from app.retrieval.search import Candidate
from app.router import Route, draft_with_context, route


# "[Insert the summary here]", "<to be filled after search>": the router left a gap to fill
PLACEHOLDER = re.compile(r"[\[<{][^\]>}]*(insert|summar|fill|placeholder|tbd|after (the )?(search|retrieval))[^\]>}]*[\]>}]", re.I)


@dataclass
class Reply:
    kind: str                         # answer, action, clarify
    text: str                         # the answer, the action summary, or the clarifying question
    answer: Answer | None = None
    action: dict | None = None        # {id, tool, server, summary, arguments} for the confirm card
    prompt_tokens: int = 0
    completion_tokens: int = 0
    trace_id: str | None = None
    trace_url: str | None = None
    sources: list[Candidate] = field(default_factory=list)


class State(TypedDict, total=False):
    message: str
    user: User
    scope: Scope
    route: Route
    chunks: list[Candidate]
    reply: Reply


@observe(name="route")
def route_node(state: State) -> State:
    with connect() as conn:
        scope = scope_for(conn, state["user"])
    return {"scope": scope, "route": route(state["message"], scope)}


@observe(name="retrieve", as_type="retriever")
def retrieve_node(state: State) -> State:
    with connect() as conn:
        return {"chunks": retrieve(conn, state["route"].question, search_roles(state["user"]))}


@observe(name="answer")
def answer_node(state: State) -> State:
    r = state["route"]
    answer = generate_answer(r.question, state["chunks"])
    return {"reply": Reply(kind="answer", text=answer.text, answer=answer, sources=answer.sources,
                           prompt_tokens=answer.prompt_tokens + r.prompt_tokens,
                           completion_tokens=answer.completion_tokens + r.completion_tokens)}


@observe(name="propose-action")
def action_node(state: State) -> State:
    """Draft the action (searching first when it needs facts), check it, and save it as proposed."""
    r, user, scope = state["route"], state["user"], state["scope"]
    sources: list[Candidate] = []
    # A placeholder ("[insert summary here]") means the facts must come from company knowledge first.
    # An empty text only means the person said little: use their own words, don't search.
    for key in ("description", "body", "text"):
        value = r.arguments.get(key)
        if isinstance(value, str) and PLACEHOLDER.search(value) and not r.context_query:
            r.context_query = state["message"]
        elif key in r.arguments and isinstance(value, str) and not value.strip():
            r.arguments[key] = state["message"]
    if r.tool == "save_work_item" and "work_item_iid" not in r.arguments and not r.arguments.get("description"):
        r.arguments["description"] = state["message"]
    if r.context_query:
        with connect() as conn:
            sources = retrieve(conn, r.context_query, search_roles(user))
        if sources:
            r = draft_with_context(state["message"], r, format_sources(sources))
    try:
        tool = check(scope, user, r.tool, r.arguments)
    except ActionRefused as e:
        return {"reply": Reply(kind="clarify", text=f"I can't do that: {e}", prompt_tokens=r.prompt_tokens,
                               completion_tokens=r.completion_tokens)}
    summary = r.summary or f"Run {tool.name}"
    with connect() as conn:
        action_id = conn.execute(
            "INSERT INTO actions (user_id, tool_id, server_name, tool_name, message, summary, arguments) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id::text",
            (user.id, tool.id, tool.server_name, tool.name, state["message"], summary, json.dumps(r.arguments)),
        ).fetchone()[0]
    action = {"id": action_id, "tool": tool.name, "server": tool.server_name, "summary": summary,
              "arguments": r.arguments, "status": "proposed", "target": _target(scope, r.arguments),
              "signature": f"Created with GitMore on behalf of {user.name}"}
    return {"reply": Reply(kind="action", text=summary, action=action, sources=sources,
                           prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens)}


def _target(scope: Scope, arguments: dict) -> str:
    """Where the action lands, in words: "engineering", "engineering · issue #7"."""
    project = next((p.name for p in scope.projects if str(arguments.get("project_id")) in (p.id, p.path, p.name)), "")
    iid = arguments.get("work_item_iid")
    return " · ".join(part for part in (project, f"issue #{iid}" if iid else "") if part)


@observe(name="clarify")
def clarify_node(state: State) -> State:
    r = state["route"]
    return {"reply": Reply(kind="clarify", text=r.clarify, prompt_tokens=r.prompt_tokens,
                           completion_tokens=r.completion_tokens)}


def build_graph():
    graph = StateGraph(State)
    graph.add_node("route", route_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("answer", answer_node)
    graph.add_node("propose", action_node)
    graph.add_node("clarify", clarify_node)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", lambda s: s["route"].kind,
                                {"knowledge": "retrieve", "action": "propose", "clarify": "clarify"})
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    graph.add_edge("propose", END)
    graph.add_edge("clarify", END)
    return graph.compile()


GRAPH = build_graph()


@observe(name="message")
def _ask(message: str, user: User) -> Reply:
    reply = GRAPH.invoke({"message": message, "user": user})["reply"]
    langfuse = get_client()
    reply.trace_id = langfuse.get_current_trace_id()
    reply.trace_url = langfuse.get_trace_url(trace_id=reply.trace_id) if reply.trace_id else None
    return reply


def ask(message: str, user: User) -> Reply:
    """Handle one chat message for this person. Their roles come from the database, never the request."""
    with propagate_attributes(user_id=user.email, metadata={"roles": ",".join(user.roles)}):
        return _ask(message, user)


@observe(name="question")
def ask_as(question: str, roles: list[str]) -> Answer:
    """Knowledge only, for scripts and evaluation: answer as someone with these roles."""
    with connect() as conn:
        chunks = retrieve(conn, question, roles)
    return generate_answer(question, chunks)
