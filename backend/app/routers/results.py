"""Results tables: CSV or XLSX uploads that become citable numbers and insertable tables."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_db
from ..deps import current_user
from ..figures import tables as svc
from ..models import User
from .projects import get_owned

router = APIRouter(prefix="/api/projects/{slug}/results", tags=["results"])

MAX_BYTES = 10 * 1024 * 1024


class CaptionIn(BaseModel):
    caption: str = Field(default="", max_length=400)


def _root(db: Session, user: User, slug: str):
    p = get_owned(db, user, slug)
    return p, storage.project_dir(p.slug)


@router.get("")
def list_tables(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return svc.load(root)


@router.post("/upload", status_code=201)
async def upload(
    slug: str,
    file: UploadFile = File(...),
    caption: str = Form(""),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _, root = _root(db, user, slug)
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File larger than 10 MB")
    try:
        return svc.create(root, file.filename or "table.csv", data, caption[:400])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # a corrupt workbook, a binary file with a .csv name
        raise HTTPException(400, f"Could not read the file: {type(e).__name__}") from e


@router.get("/{name}/preview")
def preview(slug: str, name: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    try:
        cols, rows = svc.read_rows(root, name)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"columns": cols, "rows": rows[: svc.PREVIEW_ROWS], "total": len(rows)}


@router.get("/{name}/snippet")
def snippet(slug: str, name: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    try:
        return {"markdown": svc.insert_snippet(root, name)}
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.patch("/{name}")
def update(slug: str, name: str, body: CaptionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    try:
        return svc.update(root, name, body.caption)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.delete("/{name}", status_code=204)
def delete(slug: str, name: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    if not svc.delete(root, name):
        raise HTTPException(404, "Table not found")
