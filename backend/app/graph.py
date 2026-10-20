"""The question-answering graph. Step 3 has the knowledge route only:

    START → retrieve → answer → END

The router (knowledge / action / clarify) is added in step 8. Each node is traced in
Langfuse with @observe, nested under one trace per question.
"""

from typing import TypedDict

from langfuse import observe
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
def ask(question: str, roles: list[str] | None = None) -> Answer:
    state = GRAPH.invoke({"question": question, "roles": roles or ["all"]})
    return state["answer"]
