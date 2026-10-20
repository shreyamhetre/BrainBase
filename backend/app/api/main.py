"""GitMore HTTP API.

Run (from the project root):
    uvicorn app.api.main:app --reload --reload-dir backend/app

Then open http://localhost:8000/docs to try it in the browser.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langfuse import get_client
from pydantic import BaseModel, Field

from app.embedding import get_model
from app.graph import ask
from app.retrieval.rank import get_reranker


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_model()      # load both models once at startup, not on the first request
    get_reranker()
    yield
    get_client().flush()  # send any remaining traces to Langfuse on shutdown


app = FastAPI(
    title="GitMore API",
    description="Unofficial company brain over GitLab's public handbook. Not affiliated with GitLab.",
    version="0.1.0",
    lifespan=lifespan,
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, examples=["How many weeks of parental leave do I get?"])
    role: str = Field(default="all", description="Role to ask as; permissions arrive in step 6")


class Source(BaseModel):
    number: int
    title: str
    heading_path: str
    link: str
    cited: bool
    updated_at: str | None
    status: str | None


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]
    prompt_tokens: int
    completion_tokens: int
    seconds: float


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest) -> AskResponse:
    # A plain def (not async): FastAPI runs it in a worker thread, so the
    # GPU and database work doesn't block the server.
    start = time.perf_counter()
    answer = ask(request.question, [request.role])
    return AskResponse(
        answer=answer.text,
        sources=[
            Source(
                number=n,
                title=c.title,
                heading_path=c.heading_path,
                link=c.link,
                cited=n in answer.cited,
                updated_at=c.updated_at.date().isoformat() if c.updated_at else None,
                status=c.status,
            )
            for n, c in enumerate(answer.sources, 1)
        ],
        prompt_tokens=answer.prompt_tokens,
        completion_tokens=answer.completion_tokens,
        seconds=round(time.perf_counter() - start, 2),
    )
