"""GitMore HTTP API.

Run (from the project root):
    uvicorn app.api.main:app --reload --reload-dir backend/app

Then open http://localhost:8000/docs to try it in the browser.
"""

import json
import logging
import queue
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from langfuse import get_client
from pydantic import BaseModel, Field

from app.api import (account_routes, actions_routes, admin_routes, auth_routes, conversations_routes,
                     knowledge_routes, mcp_routes, settings_routes)
from app.auth import User, current_user
from app.config import SYNC_SCHEDULER
from app.connectors.sync import Scheduler
from app.embedding import get_model
from app.graph import ask
from app.retrieval.rank import get_reranker
from app.conversations import get_or_create, history, save_turn
from app.db.connection import connect
from app.usage import log_question

log = logging.getLogger("gitmore")


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_model()      # load both models once at startup, not on the first request
    get_reranker()
    if not get_client().auth_check():  # traces are dropped while Langfuse is down; the usage log still records
        log.warning("Langfuse isn't reachable: start it with docker compose -f docker-compose.langfuse.yml up -d")
    scheduler = Scheduler() if SYNC_SCHEDULER else None
    if scheduler:
        scheduler.start()  # syncs connectors whose interval has passed, checked every minute
    yield
    if scheduler:
        scheduler.stop()
    get_client().flush()  # send any remaining traces to Langfuse on shutdown


app = FastAPI(
    title="GitMore API",
    description="Unofficial company brain over GitLab's public handbook. Not affiliated with GitLab.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(account_routes.router)
app.include_router(settings_routes.router)
app.include_router(mcp_routes.router)
app.include_router(actions_routes.router)
app.include_router(conversations_routes.router)
app.include_router(knowledge_routes.router)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000, examples=["How many weeks of parental leave do I get?"])
    conversation_id: str | None = None   # continue this chat; a new one is started when missing


class Source(BaseModel):
    number: int
    source: str
    title: str
    heading_path: str
    link: str
    cited: bool
    updated_at: str | None
    status: str | None


class ProposedAction(BaseModel):
    id: str
    tool: str
    server: str
    summary: str
    arguments: dict
    status: str
    target: str = ""        # where it lands, e.g. "engineering · issue #7"
    signature: str = ""     # the line GitMore adds to the text


class AskResponse(BaseModel):
    conversation_id: str
    kind: str                       # answer, action, choose, clarify, chat
    answer: str                     # the answer, the action summary, or the clarifying question
    sources: list[Source]
    action: ProposedAction | None = None
    question: str = ""              # choose: what "Explain the process" searches for
    offer_tool: str = ""            # answer: a tool that could do what they asked how to do
    prompt_tokens: int
    completion_tokens: int
    seconds: float


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _finish(request: AskRequest, user: User, conversation_id: str, reply, seconds: float) -> AskResponse:
    """Turn a graph reply into the response, and record it in the usage log and the chat."""
    log_question(user.id, request.question, reply, seconds)
    cited = set(reply.answer.cited) if reply.answer else set()
    response = AskResponse(
        conversation_id=conversation_id,
        kind=reply.kind,
        answer=reply.text,
        sources=[
            Source(
                number=n,
                source=c.source,
                title=c.title,
                heading_path=c.heading_path,
                link=c.link,
                cited=n in cited,
                updated_at=c.updated_at.date().isoformat() if c.updated_at else None,
                status=c.status,
            )
            for n, c in enumerate(reply.sources, 1)
        ],
        action=ProposedAction(**reply.action) if reply.action else None,
        question=reply.question,
        offer_tool=reply.offer_tool,
        prompt_tokens=reply.prompt_tokens,
        completion_tokens=reply.completion_tokens,
        seconds=seconds,
    )
    with connect() as conn:
        save_turn(conn, conversation_id, request.question, reply.kind, reply.text,
                  response.model_dump(include={"sources", "action", "question", "offer_tool", "prompt_tokens",
                                               "completion_tokens", "seconds"}))
    return response


def _start(request: AskRequest, user: User) -> tuple[str, list[dict]]:
    with connect() as conn:
        conversation_id = get_or_create(conn, user.id, request.conversation_id, request.question)
        return conversation_id, history(conn, conversation_id)  # history is read before saving this turn


@app.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest, user: User = Depends(current_user)) -> AskResponse:
    """One chat message: the router answers it, proposes an action to confirm, or asks back.

    A plain def (not async): FastAPI runs it in a worker thread, so the GPU and database work
    doesn't block the server. Roles come from the database for the logged-in user, never the request.
    """
    start = time.perf_counter()
    conversation_id, earlier = _start(request, user)
    reply = ask(request.question, user, earlier, conversation_id)
    return _finish(request, user, conversation_id, reply, round(time.perf_counter() - start, 2))


def _event(name: str, data) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


@app.post("/ask/stream")
def ask_question_stream(request: AskRequest, user: User = Depends(current_user)) -> StreamingResponse:
    """The same as /ask, streamed as server-sent events: "text" pieces of the answer while GPT writes it,
    then "done" with the full response (sources, action, tokens), or "error"."""
    start = time.perf_counter()
    conversation_id, earlier = _start(request, user)
    pieces: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            reply = ask(request.question, user, earlier, conversation_id, on_text=lambda t: pieces.put(("text", t)))
            done = _finish(request, user, conversation_id, reply, round(time.perf_counter() - start, 2))
            pieces.put(("done", done.model_dump(mode="json")))
        except Exception as e:  # tell the browser instead of leaving it waiting
            log.exception("streamed answer failed")
            pieces.put(("error", {"detail": str(e) or "Something went wrong"}))

    threading.Thread(target=work, name="ask-stream", daemon=True).start()

    def events():
        yield _event("start", {"conversation_id": conversation_id})
        while True:
            name, data = pieces.get()
            yield _event(name, data)
            if name in ("done", "error"):
                return

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
