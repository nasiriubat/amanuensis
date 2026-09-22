from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Job, User, iso

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs(project_id: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Job)
    if user.role != "admin":
        q = q.where(Job.user_id == user.id)
    if project_id:
        q = q.where(Job.project_id == project_id)
    jobs = db.scalars(q.order_by(Job.created_at.desc()).limit(50)).all()
    return [
        {
            "id": j.id,
            "type": j.type,
            "status": j.status,
            "progress": j.progress,
            "message": j.message,
            "error": j.error,
            "project_id": j.project_id,
            "profile_id": j.profile_id,
            "created_at": iso(j.created_at),
            "updated_at": iso(j.updated_at),
        }
        for j in jobs
    ]
