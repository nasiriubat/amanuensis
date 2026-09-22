from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import kinds, storage
from ..db import get_db
from ..deps import current_user, require_admin
from ..models import Project, User
from ..schemas import FileContent, KindCreate, KindOut, KindSummary

router = APIRouter(prefix="/api", tags=["kinds"])


@router.get("/kinds", response_model=list[KindSummary])
def list_kinds(_: User = Depends(current_user)):
    return kinds.list_kinds()


@router.get("/kinds/{slug}", response_model=KindOut)
def get_kind(slug: str, _: User = Depends(current_user)):
    if not kinds.kind_exists(slug):
        raise HTTPException(404, "Kind not found")
    return kinds.read_kind(slug)


@router.post("/kinds", response_model=KindOut, status_code=201)
def create_kind(body: KindCreate, _: User = Depends(require_admin)):
    return kinds.create_kind(body.name, body.summary)


@router.put("/kinds/{slug}/files/{filename}", response_model=FileContent)
def put_kind_file(slug: str, filename: str, body: FileContent, _: User = Depends(require_admin)):
    if not kinds.kind_exists(slug):
        raise HTTPException(404, "Kind not found")
    try:
        kinds.write_kind_file(slug, filename, body.content)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return body


@router.post("/kinds/{slug}/reset", response_model=KindOut)
def reset_kind(slug: str, _: User = Depends(require_admin)):
    try:
        kinds.reset_kind(slug)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return kinds.read_kind(slug)


@router.delete("/kinds/{slug}", status_code=204)
def delete_kind(slug: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not kinds.kind_exists(slug):
        raise HTTPException(404, "Kind not found")
    in_use = db.scalar(select(Project).where(Project.kind == slug))
    if in_use:
        raise HTTPException(409, "Projects still use this kind. Change their kind first.")
    try:
        kinds.delete_kind(slug)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ---------------------------------------------------------------- house style


@router.get("/house-style", response_model=FileContent)
def get_house_style(_: User = Depends(current_user)):
    return FileContent(content=storage.read_text(storage.house_style_path()))


@router.put("/house-style", response_model=FileContent)
def put_house_style(body: FileContent, _: User = Depends(require_admin)):
    storage.write_text(storage.house_style_path(), body.content)
    return body
