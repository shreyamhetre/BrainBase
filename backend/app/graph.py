"""The question-answering graph. For now the knowledge route only:

    START → retrieve → answer → END

The router (knowledge / action / clarify) comes with the MCP actions. Each node is traced in
Langfuse with @observe, nested under one trace per question, tagged with the user who asked.
"""

from typing import TypedDict

from langfuse import get_client, observe, propagate_attributes
from langgraph.graph import END, START, StateGraph

from app.db.connection import connect
from app.generation.answer import Answer, generate_answer
from app.retrieval.retrieve import retrieve
from app.retrieval.search import Candidate


class State(TypedDict, total=False):
    question: str
    roles: list[str]
    chunks: list[Candidate]
    answer: Answer


@observe(name="retrieve", as_type="retriever")
def retrieve_node(state: State) -> State:
    with connect() as conn:
        return {"chunks": retrieve(conn, state["question"], state["roles"])}


@observe(name="answer")
def answer_node(state: State) -> State:
    return {"answer": generate_answer(state["question"], state["chunks"])}


def build_graph():
    graph = StateGraph(State)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("answer", answer_node)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    return graph.compile()


GRAPH = build_graph()


@observe(name="question")
def _ask(question: str, roles: list[str]) -> Answer:
    answer = GRAPH.invoke({"question": question, "roles": roles})["answer"]
    langfuse = get_client()
    answer.trace_id = langfuse.get_current_trace_id()
    answer.trace_url = langfuse.get_trace_url(trace_id=answer.trace_id) if answer.trace_id else None
    return answer


def ask(question: str, roles: list[str] | None = None, user_email: str | None = None) -> Answer:
    """Answer one question for someone with these roles. user_email labels the Langfuse trace."""
    with propagate_attributes(user_id=user_email, metadata={"roles": ",".join(roles or [])}):
        return _ask(question, roles or ["all"])
