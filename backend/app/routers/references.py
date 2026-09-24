from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_db
from ..deps import current_user
from ..jobs import create_job, job_dict, start_job
from ..models import User
from ..refs import scan as scan_svc
from ..refs import service as svc
from ..security import llm_limiter
from .projects import get_owned

router = APIRouter(prefix="/api/projects/{slug}/references", tags=["references"])


class SearchIn(BaseModel):
    q: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=12, ge=1, le=25)


class AcceptIn(BaseModel):
    candidate: dict
    key: str | None = Field(default=None, max_length=80)


class ManualIn(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    authors: list[str] = Field(default_factory=list, max_length=50)
    year: int | None = Field(default=None, ge=1800, le=2100)
    venue: str | None = Field(default=None, max_length=300)
    doi: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    key: str | None = Field(default=None, max_length=80)
    bibtype: str = Field(default="misc", max_length=30)


class AdoptIn(BaseModel):
    idx: list[int] = Field(min_length=1, max_length=60)
    as_reference: bool = True
    as_exemplar: bool = False


def _root(db: Session, user: User, slug: str):
    p = get_owned(db, user, slug)
    return p, storage.project_dir(p.slug)


# ------------------------------------------------------------------ literature scan


@router.get("/scan")
def get_scan(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return {"scan": scan_svc.load_scan(root)}


@router.post("/scan", status_code=202)
async def run_scan(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p, _ = _root(db, user, slug)
    if not llm_limiter.allow(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down")
    job = create_job(db, user_id=user.id, type="scan", project_id=p.id, message="Queued literature scan")
    start_job(job, lambda ctx: scan_svc.run_scan(p.id, ctx))
    return job_dict(job)


@router.post("/scan/adopt")
async def adopt(slug: str, body: AdoptIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Turn chosen scan candidates into references and/or queue them as exemplars."""
    from .papers import start_exemplar_ingest, start_exemplar_pdf_ingest

    p, root = _root(db, user, slug)
    data = scan_svc.load_scan(root)
    if not data:
        raise HTTPException(404, "No scan yet")
    added: list[str] = []
    jobs: list[dict] = []
    skipped: list[str] = []
    if body.as_reference:
        added = scan_svc.adopt_references(root, body.idx)
    if body.as_exemplar:
        for i in body.idx:
            if not 0 <= i < len(data["candidates"]):
                continue
            c = data["candidates"][i]
            if c.get("adopted_exemplar") or c.get("already_exemplar"):
                continue
            if c.get("arxiv_id"):
                jobs.append(start_exemplar_ingest(db, user, p, c["arxiv_id"]))
            elif c.get("pdf_url"):
                jobs.append(start_exemplar_pdf_ingest(db, user, p, c["pdf_url"], c.get("title") or ""))
            else:
                skipped.append(c.get("title") or f"#{i}")
                continue
            scan_svc.mark_exemplar(root, i)
    if added:
        storage.git_commit(root, f"Adopt {len(added)} reference(s) from literature scan")
    return {"references": added, "jobs": jobs, "skipped": skipped}


@router.get("")
def list_refs(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    used = svc.usage(root)
    return [{**r, "uses": used.get(r["key"], 0)} for r in svc.list_records(root)]


@router.get("/requests")
def list_requests(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return svc.requests(root)


@router.get("/bib", response_class=PlainTextResponse)
def get_bib(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return storage.read_text(root / "references" / "refs.bib")


@router.post("/search")
async def search(slug: str, body: SearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _root(db, user, slug)
    return await svc.run_search(body.q, body.limit)


@router.post("", status_code=201)
def accept(slug: str, body: AcceptIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    try:
        return svc.accept(root, body.candidate, key=body.key)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/manual", status_code=201)
def manual(slug: str, body: ManualIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    try:
        return svc.add_manual(root, body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/import-bib")
async def import_bib(
    slug: str, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, root = _root(db, user, slug)
    if not (file.filename or "").lower().endswith((".bib", ".txt")):
        raise HTTPException(400, "Upload a .bib file")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "That .bib is larger than 5 MB")
    if b"\x00" in data[:4096]:
        raise HTTPException(400, "That file is not text")
    text = data.decode("utf-8", errors="ignore")
    if "@" not in text:
        raise HTTPException(400, "No BibTeX entries found in that file")
    return svc.import_bib(root, text)


@router.delete("/{key}", status_code=204)
def delete(slug: str, key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    if not svc.delete(root, key):
        raise HTTPException(404, "Reference not found")
