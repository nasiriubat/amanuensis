from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_db
from ..deps import current_user
from ..figures import service as svc
from ..llm.base import LLMError
from ..models import User
from ..security import llm_limiter
from .projects import get_owned

router = APIRouter(prefix="/api/projects/{slug}/figures", tags=["figures"])


class MermaidIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    caption: str = Field(default="", max_length=600)
    source: str = Field(min_length=1, max_length=20_000)


class FigureUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=600)
    source: str | None = Field(default=None, max_length=20_000)


class GenerateIn(BaseModel):
    prompt: str = Field(default="", max_length=1000)
    diagram: str = Field(default="architecture", pattern="^(architecture|flow|sequence|other)$")


def _root(db: Session, user: User, slug: str):
    p = get_owned(db, user, slug)
    return p, storage.project_dir(p.slug)


@router.get("")
def list_figures(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return [{**f, "source": svc.source(root, f)} for f in svc.load(root)]


@router.post("/mermaid", status_code=201)
def create_mermaid(slug: str, body: MermaidIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    item = svc.create_mermaid(root, body.name, body.caption, body.source)
    return {**item, "source": body.source}


@router.post("/generate")
async def generate(slug: str, body: GenerateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p, _ = _root(db, user, slug)
    if not llm_limiter.allow(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down")
    try:
        return {"source": await svc.generate_mermaid(p.id, user.id, body.prompt, body.diagram)}
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e


@router.post("/upload", status_code=201)
async def upload(
    slug: str,
    file: UploadFile = File(...),
    name: str = Form(...),
    caption: str = Form(""),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, root = _root(db, user, slug)
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Image larger than 20 MB")
    try:
        return svc.create_image(root, name, caption, data, file.content_type or "")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.patch("/{name}")
def update_figure(
    slug: str, name: str, body: FigureUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, root = _root(db, user, slug)
    try:
        item = svc.update(root, name, caption=body.caption, source=body.source)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {**item, "source": svc.source(root, item)}


@router.post("/{name}/render")
async def store_render(
    slug: str,
    name: str,
    svg: UploadFile | None = File(default=None),
    png: UploadFile | None = File(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, root = _root(db, user, slug)
    svg_bytes = await svg.read() if svg else None
    png_bytes = await png.read() if png else None
    if svg_bytes and not svg_bytes.lstrip().startswith(b"<"):
        raise HTTPException(400, "That is not an SVG")
    if png_bytes and png_bytes[:4] != b"\x89PNG":
        raise HTTPException(400, "That is not a PNG")
    try:
        return svc.store_render(root, name, svg_bytes, png_bytes)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{name}/file")
def figure_file(
    slug: str, name: str, kind: str = "file", user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, root = _root(db, user, slug)
    p = svc.file_path(root, name, "png_file" if kind == "png" else "file")
    if not p:
        raise HTTPException(404, "Not rendered yet")
    return FileResponse(p, headers={"Cache-Control": "no-cache"})


@router.delete("/{name}", status_code=204)
def delete_figure(slug: str, name: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    if not svc.delete(root, name):
        raise HTTPException(404, "Figure not found")
