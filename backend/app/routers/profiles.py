from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_db
from ..deps import current_user
from ..models import AuthorProfile, User
from ..schemas import FileContent, ProfileCreate, ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _out(p: AuthorProfile) -> ProfileOut:
    sources = storage.profile_dir(p.slug) / "sources"
    # each source paper is a folder (extracted.md, meta.json, ...); ignore stray files and dot dirs
    count = len([f for f in sources.iterdir() if f.is_dir() and not f.name.startswith(".")]) if sources.exists() else 0
    return ProfileOut(
        id=p.id,
        slug=p.slug,
        name=p.name,
        description=p.description,
        owner_id=p.owner_id,
        owner_name=p.owner.display_name,
        shareable=p.shareable,
        status=p.status,
        source_count=count,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def visible(db: Session, user: User):
    q = select(AuthorProfile)
    if user.role != "admin":
        q = q.where(or_(AuthorProfile.owner_id == user.id, AuthorProfile.shareable.is_(True)))
    return q.order_by(AuthorProfile.updated_at.desc())


def get_visible(db: Session, user: User, slug: str) -> AuthorProfile:
    p = db.scalar(select(AuthorProfile).where(AuthorProfile.slug == slug))
    if not p:
        raise HTTPException(404, "Profile not found")
    if user.role != "admin" and p.owner_id != user.id and not p.shareable:
        raise HTTPException(404, "Profile not found")
    return p


def require_owner(p: AuthorProfile, user: User) -> None:
    if user.role != "admin" and p.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can change this profile")


@router.get("", response_model=list[ProfileOut])
def list_profiles(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [_out(p) for p in db.scalars(visible(db, user)).all()]


@router.post("", response_model=ProfileOut, status_code=201)
def create_profile(body: ProfileCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    base = storage.slugify(body.name)
    slug = storage.unique_slug(
        base, lambda s: db.scalar(select(AuthorProfile).where(AuthorProfile.slug == s)) is not None
    )
    p = AuthorProfile(
        slug=slug, name=body.name, description=body.description, owner_id=user.id, shareable=body.shareable
    )
    db.add(p)
    db.flush()
    storage.create_profile_tree(slug, {"id": p.id, "name": p.name, "owner": user.email})
    db.commit()
    db.refresh(p)
    return _out(p)


@router.get("/{slug}", response_model=ProfileOut)
def get_profile(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _out(get_visible(db, user, slug))


@router.patch("/{slug}", response_model=ProfileOut)
def update_profile(slug: str, body: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_visible(db, user, slug)
    require_owner(p, user)
    if body.name is not None:
        p.name = body.name
    if body.description is not None:
        p.description = body.description
    if body.shareable is not None:
        p.shareable = body.shareable
    db.commit()
    db.refresh(p)
    return _out(p)


@router.delete("/{slug}", status_code=204)
def delete_profile(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_visible(db, user, slug)
    require_owner(p, user)
    db.delete(p)
    db.commit()
    storage.delete_profile_tree(slug)


@router.get("/{slug}/style", response_model=FileContent)
def get_style(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_visible(db, user, slug)
    return FileContent(content=storage.read_text(storage.profile_dir(p.slug) / "style.md"))


@router.put("/{slug}/style", response_model=FileContent)
def put_style(slug: str, body: FileContent, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_visible(db, user, slug)
    require_owner(p, user)
    root = storage.profile_dir(p.slug)
    storage.write_text(root / "style.md", body.content)
    storage.git_commit(root, "Edit style.md")
    if body.content.strip() and p.status == "empty":
        p.status = "ready"
        db.commit()
    return body
