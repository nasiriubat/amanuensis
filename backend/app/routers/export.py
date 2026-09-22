from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_db
from ..deps import current_user, require_admin
from ..export import service as svc
from ..jobs import create_job, job_dict, start_job
from ..models import User
from .projects import get_owned

router = APIRouter(prefix="/api", tags=["export"])


class Author(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    affiliation: str = Field(default="", max_length=200)
    email: str = Field(default="", max_length=120)
    country: str = Field(default="", max_length=80)
    orcid: str = Field(default="", max_length=40)


class PaperMetaIn(BaseModel):
    authors: list[Author] = Field(default_factory=list, max_length=20)
    keywords: list[str] = Field(default_factory=list, max_length=12)
    subtitle: str = Field(default="", max_length=200)


class ExportIn(BaseModel):
    template: str = Field(min_length=1, max_length=60)
    formats: list[str] = Field(default_factory=lambda: ["pdf", "docx"])


class CustomTemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    class_name: str = Field(default="article", max_length=60)
    bib_style: str = Field(default="plain", max_length=60)
    wrapper: str = Field(min_length=20, max_length=50_000)


# ------------------------------------------------------------------ templates


@router.get("/templates")
def list_templates(_: User = Depends(current_user)):
    return {"templates": svc.list_templates(), "tools": svc.tools_status()}


@router.post("/templates", status_code=201)
def create_template(body: CustomTemplateIn, _: User = Depends(require_admin)):
    return svc.create_custom_template(body.name, body.description, body.class_name, body.bib_style, body.wrapper)


@router.post("/templates/{slug}/files")
async def upload_template_file(slug: str, file: UploadFile = File(...), _: User = Depends(require_admin)):
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "File larger than 5 MB")
    try:
        svc.add_template_file(slug, file.filename or "file", data)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return svc.template(slug)


# ------------------------------------------------------------------ per project


def _root(db: Session, user: User, slug: str):
    p = get_owned(db, user, slug)
    return p, storage.project_dir(p.slug)


@router.get("/projects/{slug}/paper-meta")
def get_meta(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return svc.paper_meta(root)


@router.put("/projects/{slug}/paper-meta")
def put_meta(slug: str, body: PaperMetaIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return svc.save_paper_meta(root, body.model_dump())


@router.get("/projects/{slug}/exports")
def list_exports(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return svc.list_exports(root)


@router.post("/projects/{slug}/exports", status_code=202)
async def start_export(slug: str, body: ExportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p, _ = _root(db, user, slug)
    if not svc.template(body.template):
        raise HTTPException(400, "Unknown template")
    formats = [f for f in body.formats if f in ("pdf", "docx")]
    job = create_job(db, user_id=user.id, type="export", project_id=p.id, message=f"Queued export ({body.template})")
    start_job(job, lambda ctx: svc.run_export(p.id, ctx, template_slug=body.template, formats=formats))
    return job_dict(job)


@router.get("/projects/{slug}/exports/{stamp}/{filename}")
def download(slug: str, stamp: str, filename: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    path = svc.export_file(root, stamp, filename)
    if not path:
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename=filename)
