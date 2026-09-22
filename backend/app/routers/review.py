from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_db
from ..deps import current_user
from ..jobs import create_job, job_dict, start_job
from ..llm.base import LLMError
from ..models import User
from ..security import llm_limiter
from ..studio import review as svc
from .projects import get_owned

router = APIRouter(prefix="/api/projects/{slug}", tags=["review"])


class VenueChoice(BaseModel):
    venue: str = Field(min_length=1, max_length=200)


@router.get("/review")
def get_review(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    root = storage.project_dir(p.slug)
    return {"review": svc.load_review(root), "venues": svc.load_venues(root)}


@router.post("/review", status_code=202)
async def run_review(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    if not llm_limiter.allow(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down")
    job = create_job(db, user_id=user.id, type="critique", project_id=p.id, message="Queued review")
    start_job(job, lambda ctx: svc.run_critique(p.id, ctx))
    return job_dict(job)


@router.post("/venue/suggest")
async def venue_suggest(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    if not llm_limiter.allow(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down")
    try:
        return await svc.suggest_venues(p.id, user.id)
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e


@router.post("/venue")
def set_venue(slug: str, body: VenueChoice, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    p.venue = body.venue.strip()
    db.commit()
    return {"venue": p.venue}
