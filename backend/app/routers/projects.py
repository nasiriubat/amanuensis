from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_db
from ..deps import current_user
from ..kinds import kind_exists, kind_name
from ..models import AuthorProfile, Project, User, now
from ..schemas import FileContent, ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])

# Files a user may read and edit directly in phase 1. Sections and exemplars get their own
# endpoints in later phases.
EDITABLE_FILES = {
    "system-spec": "inputs/system-spec.md",
    "idea": "inputs/idea.md",
    "research-plan": "inputs/research-plan.md",
    "interview": "inputs/interview.md",
    "facts": "inputs/facts.md",
    "outline": "outline.md",
    **{f"playbook/{name[:-3]}": f"playbook/{name}" for name in storage.PLAYBOOK_FILES},
}


def _interview_rounds(root: Path) -> dict:
    p = root / "inputs" / "interview.json"
    if not p.exists():
        return {"rounds": 0, "answered": 0, "open": 0, "done": False}
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"rounds": 0, "answered": 0, "open": 0, "done": False}
    qs = [q for r in state.get("rounds", []) for q in r.get("questions", [])]
    answered = sum(1 for q in qs if q.get("status") in ("answered", "na"))
    return {
        "rounds": len(state.get("rounds", [])),
        "answered": answered,
        "open": len(qs) - answered,
        "done": bool(state.get("done")),
    }


def _sections_drafted(root: Path) -> int:
    p = root / "sections" / "index.json"
    if not p.exists():
        return 0
    try:
        return sum(
            1 for s in json.loads(p.read_text(encoding="utf-8")).get("sections", []) if s.get("status") != "empty"
        )
    except json.JSONDecodeError:
        return 0


def _checklist_open(root: Path) -> int:
    p = root / "checklist.json"
    if not p.exists():
        return 0
    try:
        return sum(1 for i in json.loads(p.read_text(encoding="utf-8")) if i.get("status") == "open")
    except (json.JSONDecodeError, AttributeError):
        return 0


def _cite_requests(root: Path) -> int:
    d = root / "sections"
    if not d.exists():
        return 0
    return sum(len(re.findall(r"\[CITE:", f.read_text(encoding="utf-8", errors="ignore"))) for f in d.glob("*.md"))


def _json_len(p: Path) -> int:
    if not p.exists():
        return 0
    try:
        return len(json.loads(p.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError):
        return 0


def _counts(slug: str) -> dict:
    root = storage.project_dir(slug)

    def count(sub: str) -> int:
        d = root / sub
        return len([f for f in d.iterdir() if not f.name.startswith(".")]) if d.exists() else 0

    playbook_filled = sum(
        1
        for n in storage.PLAYBOOK_FILES
        if (root / "playbook" / n).exists() and (root / "playbook" / n).stat().st_size > 0
    )
    return {
        "exemplars": count("exemplars"),
        "readings": count("readings"),
        "sections": len(list((root / "sections").glob("*.md"))) if (root / "sections").exists() else 0,
        "sections_drafted": _sections_drafted(root),
        "checklist_open": _checklist_open(root),
        "references": len(list((root / "references").glob("*.json"))) if (root / "references").exists() else 0,
        "cite_requests": _cite_requests(root),
        "figures": _json_len(root / "figures" / "index.json"),
        "exports": len([d for d in (root / "exports").iterdir() if d.is_dir()]) if (root / "exports").exists() else 0,
        "reviewed": (root / "review.json").exists(),
        "playbook_files": playbook_filled,
        "has_plan": (root / "inputs" / "research-plan.md").exists()
        and (root / "inputs" / "research-plan.md").stat().st_size > 0,
        "has_outline": (root / "outline.md").exists() and (root / "outline.md").stat().st_size > 0,
        "interview_rounds": _interview_rounds(root),
        "has_spec": (root / "inputs" / "system-spec.md").exists()
        and (root / "inputs" / "system-spec.md").stat().st_size > 0,
    }


def _out(p: Project) -> ProjectOut:
    return ProjectOut(
        id=p.id,
        slug=p.slug,
        title=p.title,
        owner_id=p.owner_id,
        owner_name=p.owner.display_name,
        kind=p.kind,
        kind_name=kind_name(p.kind),
        entry=p.entry or "built",
        profile_id=p.profile_id,
        profile_name=p.profile.name if p.profile else None,
        venue=p.venue,
        stage=p.stage,
        model_overrides=p.model_overrides,
        counts=_counts(p.slug),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def get_owned(db: Session, user: User, slug: str) -> Project:
    p = db.scalar(select(Project).where(Project.slug == slug))
    if not p or (user.role != "admin" and p.owner_id != user.id):
        raise HTTPException(404, "Project not found")
    return p


def _check_profile(db: Session, user: User, profile_id: str | None) -> AuthorProfile | None:
    if not profile_id:
        return None
    prof = db.get(AuthorProfile, profile_id)
    if not prof or (user.role != "admin" and prof.owner_id != user.id and not prof.shareable):
        raise HTTPException(400, "Author profile not found or not shared with you")
    return prof


@router.get("", response_model=list[ProjectOut])
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Project)
    if user.role != "admin":
        q = q.where(Project.owner_id == user.id)
    return [_out(p) for p in db.scalars(q.order_by(Project.updated_at.desc())).all()]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not kind_exists(body.kind):
        raise HTTPException(400, f"Unknown paper kind '{body.kind}'")
    _check_profile(db, user, body.profile_id)
    base = storage.slugify(body.title)
    slug = storage.unique_slug(base, lambda s: db.scalar(select(Project).where(Project.slug == s)) is not None)
    p = Project(
        slug=slug,
        title=body.title,
        owner_id=user.id,
        kind=body.kind,
        entry=body.entry,
        profile_id=body.profile_id,
        venue=body.venue,
    )
    db.add(p)
    db.flush()
    storage.create_project_tree(slug, {"id": p.id, "title": p.title, "kind": p.kind, "owner": user.email})
    db.commit()
    db.refresh(p)
    return _out(p)


@router.get("/{slug}", response_model=ProjectOut)
def get_project(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _out(get_owned(db, user, slug))


@router.patch("/{slug}", response_model=ProjectOut)
def update_project(slug: str, body: ProjectUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    if body.title is not None:
        p.title = body.title
    if body.kind is not None:
        if not kind_exists(body.kind):
            raise HTTPException(400, f"Unknown paper kind '{body.kind}'")
        p.kind = body.kind
    if body.entry is not None:
        p.entry = body.entry
    if body.clear_profile:
        p.profile_id = None
    elif body.profile_id is not None:
        _check_profile(db, user, body.profile_id)
        p.profile_id = body.profile_id
    if body.venue is not None:
        p.venue = body.venue or None
    if body.model_overrides is not None:
        p.model_overrides = body.model_overrides
    db.commit()
    db.refresh(p)
    return _out(p)


@router.delete("/{slug}", status_code=204)
def delete_project(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    if user.role != "admin" and p.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can delete a project")
    db.delete(p)
    db.commit()
    storage.delete_project_tree(slug)


@router.get("/{slug}/files/{name:path}", response_model=FileContent)
def get_file(slug: str, name: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    rel = EDITABLE_FILES.get(name)
    if not rel:
        raise HTTPException(404, "Unknown file")
    return FileContent(content=storage.read_text(storage.project_dir(p.slug) / rel))


@router.put("/{slug}/files/{name:path}", response_model=FileContent)
def put_file(
    slug: str, name: str, body: FileContent, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    p = get_owned(db, user, slug)
    rel = EDITABLE_FILES.get(name)
    if not rel:
        raise HTTPException(404, "Unknown file")
    root = storage.project_dir(p.slug)
    storage.write_text(root / rel, body.content)
    storage.git_commit(root, f"Edit {rel}")
    p.updated_at = now()
    db.commit()
    return body


@router.get("/{slug}/history")
def history(slug: str, path: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    rel = EDITABLE_FILES.get(path) if path else None
    return storage.git_log(storage.project_dir(p.slug), rel)
