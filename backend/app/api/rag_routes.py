"""Admin: RAG settings (search, answers, handbook rules) and the handbook refresh job."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app import handbook_job, rag_settings
from app.audit import record
from app.auth import User, admin_user
from app.db.connection import connect

router = APIRouter(prefix="/admin", tags=["admin"])


class SectionInfo(BaseModel):
    name: str
    pages: int        # pages in the handbook clone
    indexed: int      # pages in GitMore's index now


class RagSettingsOut(BaseModel):
    settings: dict
    defaults: dict
    limits: dict
    answer_lengths: dict
    sections: list[SectionInfo]
    handbook: dict    # indexed pages + last refresh status


def _sections() -> list[SectionInfo]:
    from app.ingestion.handbook import CONTENT
    counts: dict[str, int] = {}
    if CONTENT.exists():
        for path in CONTENT.rglob("*.md"):
            parts = path.relative_to(CONTENT).parts
            if len(parts) > 1:
                counts[parts[0]] = counts.get(parts[0], 0) + 1
    with connect() as conn:
        indexed = dict(conn.execute("SELECT section, count(*) FROM documents WHERE source = 'handbook' GROUP BY section").fetchall())
    return [SectionInfo(name=n, pages=c, indexed=indexed.get(n, 0)) for n, c in sorted(counts.items())]


def _out() -> RagSettingsOut:
    with connect() as conn:
        pages = conn.execute("SELECT count(*) FROM documents WHERE source = 'handbook'").fetchone()[0]
    return RagSettingsOut(settings=asdict(rag_settings.get()), defaults=asdict(rag_settings.RagSettings()),
                          limits={k: list(v) for k, v in rag_settings.LIMITS.items()},
                          answer_lengths=rag_settings.ANSWER_LENGTHS, sections=_sections(),
                          handbook={"indexed_pages": pages, "job": handbook_job.status()})


@router.get("/rag-settings", response_model=RagSettingsOut)
def get_settings(_: User = Depends(admin_user)) -> RagSettingsOut:
    return _out()


@router.put("/rag-settings", response_model=RagSettingsOut)
def save_settings(changes: dict, admin: User = Depends(admin_user)) -> RagSettingsOut:
    before = asdict(rag_settings.get())
    try:
        clean = rag_settings.validate(changes, [s.name for s in _sections()])
        with connect() as conn:
            rag_settings.save(conn, clean, admin.id)
            changed = {k: {"before": before[k], "after": v} for k, v in clean.items() if before[k] != v}
            if changed:
                record(conn, admin.id, "rag.settings", changed=changed)
    except rag_settings.SettingsError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    return _out()


@router.post("/handbook/refresh", status_code=status.HTTP_202_ACCEPTED)
def refresh_handbook(admin: User = Depends(admin_user)) -> dict:
    if not handbook_job.start(admin.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "A handbook refresh is already running")
    with connect() as conn:
        record(conn, admin.id, "handbook.refresh")
    return {"started": True}


@router.get("/handbook/status")
def handbook_status(_: User = Depends(admin_user)) -> dict:
    return handbook_job.status()
