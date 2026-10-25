"""The question-answering graph. The router decides the path for every message:

    START → route ─┬─ chat ──────→ reply (written by the router, no sources) ─→ END
                   ├─ knowledge → retrieve → answer ─────────────────────────→ END
                   ├─ action ───→ propose (search first if needed) ──────────→ END   (the person confirms later)
                   ├─ choose ───→ propose, and offer "explain" or "do it" ────→ END
                   └─ clarify ─────────────────────────────────────────────────→ END

A "chat" label is double-checked (chat_guard): a company question is searched instead.

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
from app.chat_guard import is_company_question
from app.auth import User, search_roles
from app.db.connection import connect
from app.generation.answer import NOT_FOUND, Answer, format_sources, generate_answer
from app.retrieval.retrieve import retrieve
from app.retrieval.search import Candidate
from app.router import Route, draft_with_context, route


# "[Insert the summary here]", "<to be filled after search>": the router left a gap to fill
PLACEHOLDER = re.compile(r"[\[<{][^\]>}]*(insert|summar|fill|placeholder|tbd|after (the )?(search|retrieval))[^\]>}]*[\]>}]", re.I)


@dataclass
class Reply:
    kind: str                         # answer, action, choose, clarify, chat
    text: str                         # the answer, the action summary, or the clarifying question
    answer: Answer | None = None
    action: dict | None = None        # {id, tool, server, summary, arguments} for the confirm card
    question: str = ""                # choose: what "Explain" will search for
    offer_tool: str = ""              # answer: a tool that could do what they asked how to do
    prompt_tokens: int = 0
    completion_tokens: int = 0
    trace_id: str | None = None
    trace_url: str | None = None
    sources: list[Candidate] = field(default_factory=list)


class State(TypedDict, total=False):
    message: str
    history: list[dict]
    user: User
    scope: Scope
    route: Route
    chunks: list[Candidate]
    reply: Reply


@observe(name="route")
def route_node(state: State) -> State:
    user = state["user"]
    with connect() as conn:
        scope = scope_for(conn, user)
        r = route(state["message"], scope, state.get("history"), person=user.name.split(" ")[0])
        if r.kind == "chat" and is_company_question(conn, state["message"]):
            r.kind, r.question, r.reply = "knowledge", state["message"], ""  # never answer the company from memory
    return {"scope": scope, "route": r}


@observe(name="retrieve", as_type="retriever")
def retrieve_node(state: State) -> State:
    with connect() as conn:
        return {"chunks": retrieve(conn, state["route"].question, search_roles(state["user"]))}


@observe(name="answer")
def answer_node(state: State) -> State:
    r = state["route"]
    answer = generate_answer(r.question, state["chunks"])
    # "Couldn't find": the chunks it looked at didn't answer the question, so don't show them as sources
    sources = [] if NOT_FOUND.rstrip(".") in answer.text else answer.sources
    return {"reply": Reply(kind="answer", text=answer.text, answer=answer, sources=sources,
                           offer_tool=r.offer_tool if sources else "",
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
        if r.kind == "choose":  # the "do it" half isn't possible: just answer the question
            r.kind = "knowledge"
            with connect() as conn:
                chunks = retrieve(conn, r.question, search_roles(user))
            return answer_node({**state, "route": r, "chunks": chunks})
        return {"reply": Reply(kind="clarify", text=f"I can't do that: {e}", prompt_tokens=r.prompt_tokens,
                               completion_tokens=r.completion_tokens)}
    summary = r.summary or f"Run {tool.name}"
    with connect() as conn:
        action_id = conn.execute(
            "INSERT INTO actions (user_id, tool_id, server_name, tool_name, message, summary, arguments) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id::text",
            (user.id, tool.id, tool.server_name, tool.name, state["message"], summary, json.dumps(r.arguments)),
        ).fetchone()[0]
    if r.kind == "choose":
        return {"reply": Reply(kind="choose", text=r.clarify, question=r.question, sources=sources,
                               action={"id": action_id, "tool": tool.name, "server": tool.server_name, "summary": summary,
                                       "arguments": r.arguments, "status": "proposed", "target": _target(scope, r.arguments),
                                       "signature": f"Created with GitMore on behalf of {user.name}"},
                               prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens)}
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


@observe(name="chat")
def chat_node(state: State) -> State:
    r = state["route"]
    return {"reply": Reply(kind="chat", text=r.reply, prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens)}


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
    graph.add_node("chat", chat_node)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", lambda s: s["route"].kind,
                                {"knowledge": "retrieve", "action": "propose", "choose": "propose",
                                 "clarify": "clarify", "chat": "chat"})
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    graph.add_edge("propose", END)
    graph.add_edge("clarify", END)
    graph.add_edge("chat", END)
    return graph.compile()


GRAPH = build_graph()


@observe(name="message")
def _ask(message: str, user: User, history: list[dict]) -> Reply:
    reply = GRAPH.invoke({"message": message, "user": user, "history": history})["reply"]
    langfuse = get_client()
    reply.trace_id = langfuse.get_current_trace_id()
    reply.trace_url = langfuse.get_trace_url(trace_id=reply.trace_id) if reply.trace_id else None
    return reply


def ask(message: str, user: User, history: list[dict] | None = None, conversation_id: str | None = None) -> Reply:
    """Handle one chat message for this person. Their roles come from the database, never the request.
    history holds the conversation's last few messages (from the database), for follow-ups."""
    with propagate_attributes(user_id=user.email, session_id=conversation_id, metadata={"roles": ",".join(user.roles)}):
        return _ask(message, user, history or [])


@observe(name="question")
def ask_as(question: str, roles: list[str]) -> Answer:
    """Knowledge only, for scripts and evaluation: answer as someone with these roles."""
    with connect() as conn:
        chunks = retrieve(conn, question, roles)
    return generate_answer(question, chunks)
