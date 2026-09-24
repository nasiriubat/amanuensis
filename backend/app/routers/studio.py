from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_db
from ..deps import current_user
from ..jobs import create_job, job_dict, start_job
from ..models import User
from ..security import llm_limiter
from ..studio import lint as lint_mod
from ..studio import service as svc
from .projects import get_owned

router = APIRouter(prefix="/api/projects/{slug}", tags=["studio"])


class SectionContent(BaseModel):
    content: str = Field(max_length=200_000)


class DraftIn(BaseModel):
    instructions: str = Field(default="", max_length=4000)
    force: bool = False


class LockIn(BaseModel):
    mine: bool


class ChecklistStatus(BaseModel):
    status: Literal["open", "resolved", "limitation"]


class ChecklistAdd(BaseModel):
    section: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=1000)


class LintIn(BaseModel):
    text: str = Field(max_length=200_000)


def _root(db: Session, user: User, slug: str):
    p = get_owned(db, user, slug)
    return p, storage.project_dir(p.slug)


def _views(root) -> dict:
    index = svc.load_index(root)
    house = storage.read_text(storage.house_style_path())
    keys = svc.known_ref_keys(root)
    exemplars = svc.exemplar_texts(root)
    return {
        "initialized": index.get("initialized_at") is not None,
        "sections": [svc.section_view(root, s, house, keys, exemplars) for s in index["sections"]],
    }


@router.get("/studio")
def get_studio(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return _views(root)


@router.post("/studio/init")
def init_studio(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p, root = _root(db, user, slug)
    if p.stage not in ("outline", "drafting", "review", "export"):
        raise HTTPException(400, "Approve the outline before starting to draft")
    try:
        svc.init_sections(root)
        svc.seed_kind_checklist(root, p.kind, svc.parse_outline(storage.read_text(root / "outline.md")))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if p.stage == "outline":
        p.stage = "drafting"
        db.commit()
    return _views(root)


class ImportIn(BaseModel):
    markdown: str = Field(min_length=1, max_length=400_000)


@router.post("/studio/import")
def import_draft(slug: str, body: ImportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """An author who already has a draft pastes it; headings become sections marked as theirs."""
    p, root = _root(db, user, slug)
    if svc.load_index(root)["sections"]:
        raise HTTPException(400, "This project already has sections. Paste text into a section in the Studio instead.")
    try:
        result = svc.import_draft(root, body.markdown, p.title)
        svc.seed_kind_checklist(root, p.kind, svc.parse_outline(storage.read_text(root / "outline.md")))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    p.stage = "drafting"
    db.commit()
    return {**_views(root), "imported": result}


@router.get("/sections/{section_id}")
def get_section(slug: str, section_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    try:
        sec = svc.get_section(root, section_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    text = svc.read_section(root, sec)
    house = storage.read_text(storage.house_style_path())
    return {
        "section": sec,
        "content": text,
        "lint": lint_mod.lint(text, house, svc.known_ref_keys(root), svc.exemplar_texts(root)),
    }


@router.put("/sections/{section_id}")
def put_section(
    slug: str, section_id: str, body: SectionContent, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, root = _root(db, user, slug)
    try:
        sec = svc.get_section(root, section_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    sec = svc.save_section_text(root, sec, body.content, by_user=True)
    house = storage.read_text(storage.house_style_path())
    return {
        "section": sec,
        "content": body.content,
        "lint": lint_mod.lint(body.content, house, svc.known_ref_keys(root), svc.exemplar_texts(root)),
    }


@router.post("/sections/{section_id}/lock")
def lock_section(
    slug: str, section_id: str, body: LockIn, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, root = _root(db, user, slug)
    try:
        sec = svc.get_section(root, section_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    has_text = bool(svc.read_section(root, sec).strip())
    new_status = "mine" if body.mine else ("edited" if has_text else "empty")
    sec = svc.update_section_meta(root, section_id, status=new_status)
    storage.git_commit(root, f"{'Lock' if body.mine else 'Unlock'} section: {sec['title']}")
    return sec


@router.post("/sections/{section_id}/draft", status_code=202)
async def draft_section(
    slug: str,
    section_id: str,
    body: DraftIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    p, root = _root(db, user, slug)
    if not llm_limiter.allow(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down")
    try:
        sec = svc.get_section(root, section_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    body = body or DraftIn()
    if sec["status"] == "mine" and not body.force:
        raise HTTPException(409, "This section is marked as yours. Confirm to regenerate it.")
    job = create_job(db, user_id=user.id, type="draft_section", project_id=p.id, message=f"Queued: {sec['title']}")
    start_job(
        job, lambda ctx: svc.draft_section(p.id, section_id, ctx, instructions=body.instructions, force=body.force)
    )
    return job_dict(job)


@router.get("/sections/{section_id}/history")
def section_history(slug: str, section_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    try:
        sec = svc.get_section(root, section_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return svc.history(root, sec)


@router.get("/sections/{section_id}/versions/{sha}")
def section_version(
    slug: str, section_id: str, sha: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, root = _root(db, user, slug)
    try:
        sec = svc.get_section(root, section_id)
        return {"sha": sha, "content": svc.version_text(root, sec, sha)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ------------------------------------------------------------------ checklist


@router.get("/checklist")
def get_checklist(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return svc.load_checklist(root)


@router.patch("/checklist/{item_id}")
def patch_checklist(
    slug: str, item_id: str, body: ChecklistStatus, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    _, root = _root(db, user, slug)
    try:
        it = svc.set_checklist_status(root, item_id, body.status)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    storage.git_commit(root, f"Checklist: {body.status}: {it['text'][:50]}")
    return it


@router.post("/checklist", status_code=201)
def add_checklist(slug: str, body: ChecklistAdd, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    return svc.add_checklist_item(root, body.section, body.text)


# ------------------------------------------------------------------ lint


@router.post("/lint")
def lint_text(slug: str, body: LintIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _, root = _root(db, user, slug)
    house = storage.read_text(storage.house_style_path())
    return lint_mod.lint(body.text, house, svc.known_ref_keys(root), svc.exemplar_texts(root))
