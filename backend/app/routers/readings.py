"""Background reading: papers the author read, ingested in full, carded, and citable."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_db
from ..deps import current_user
from ..ingest import service as ingest
from ..ingest.arxiv import parse_arxiv_id
from ..jobs import create_job, job_dict, start_job
from ..models import User
from ..refs import readings as svc
from ..security import llm_limiter
from .papers import ArxivIn, _read_pdf
from .projects import get_owned

router = APIRouter(prefix="/api/projects/{slug}/readings", tags=["readings"])


def start_reading_ingest(
    db: Session, user: User, project, *, arxiv_id: str | None = None, pdf_url: str | None = None, title: str = ""
) -> dict:
    """Queue one reading from arXiv or an open PDF. Shared with the literature scan."""
    label = arxiv_id or title or pdf_url or "paper"
    job = create_job(db, user_id=user.id, type="ingest_reading", project_id=project.id, message=f"Queued {label}"[:200])
    start_job(job, lambda ctx: svc.ingest_reading(project.id, ctx, arxiv_id=arxiv_id, pdf_url=pdf_url, title=title))
    return job_dict(job)


@router.get("")
def list_readings(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    return svc.list_readings(storage.project_dir(p.slug))


@router.get("/{paper_id}")
def get_reading(slug: str, paper_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    root = storage.project_dir(p.slug)
    r = ingest.read_paper(svc.readings_dir(root), paper_id)
    if not r:
        raise HTTPException(404, "Reading not found")
    meta, md = r
    card = svc.load_card(svc.readings_dir(root) / paper_id)
    return {"meta": meta, "markdown": md, "summary": None, "card": card}


@router.post("/arxiv", status_code=202)
async def add_arxiv(slug: str, body: ArxivIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    aid = parse_arxiv_id(body.ref)
    if not aid:
        raise HTTPException(400, "That does not look like an arXiv id or URL")
    return start_reading_ingest(db, user, p, arxiv_id=aid)


@router.post("/upload", status_code=202)
async def add_pdf(
    slug: str, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)
):
    p = get_owned(db, user, slug)
    data = await _read_pdf(file)
    name = file.filename or "paper.pdf"
    job = create_job(db, user_id=user.id, type="ingest_reading", project_id=p.id, message=f"Queued {name}"[:200])
    start_job(job, lambda ctx: svc.ingest_reading(p.id, ctx, pdf_bytes=data, filename=name))
    return job_dict(job)


@router.post("/{paper_id}/card", status_code=202)
async def rewrite_card(slug: str, paper_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Write the card again, for example after the specification changed."""
    p = get_owned(db, user, slug)
    if not llm_limiter.allow(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down")
    root = storage.project_dir(p.slug)
    if not (svc.readings_dir(root) / paper_id).is_dir():
        raise HTTPException(404, "Reading not found")
    job = create_job(db, user_id=user.id, type="reading_card", project_id=p.id, message="Queued: reading card")
    start_job(job, lambda ctx: svc.summarise_reading(p.id, paper_id, ctx))
    return job_dict(job)


@router.delete("/{paper_id}", status_code=204)
def delete_reading(slug: str, paper_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    root = storage.project_dir(p.slug)
    if not svc.delete_reading(root, paper_id):
        raise HTTPException(404, "Reading not found")
    storage.git_commit(root, f"Remove reading {paper_id}")
