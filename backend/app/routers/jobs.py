from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from ..db import SessionLocal, get_db
from ..deps import current_user
from ..jobs import cancel_job, job_dict
from ..models import Job, User

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _owned(db: Session, user: User, job_id: str) -> Job:
    j = db.get(Job, job_id)
    if not j or (user.role != "admin" and j.user_id != user.id):
        raise HTTPException(404, "Job not found")
    return j


@router.get("")
def list_jobs(
    project_id: str | None = None,
    profile_id: str | None = None,
    active: bool = False,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = select(Job)
    if user.role != "admin":
        q = q.where(Job.user_id == user.id)
    if project_id:
        q = q.where(Job.project_id == project_id)
    if profile_id:
        q = q.where(Job.profile_id == profile_id)
    if active:
        q = q.where(Job.status.in_(["queued", "running"]))
    return [job_dict(j) for j in db.scalars(q.order_by(Job.created_at.desc()).limit(50)).all()]


@router.get("/{job_id}")
def get_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return job_dict(_owned(db, user, job_id))


@router.post("/{job_id}/cancel")
def cancel(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = _owned(db, user, job_id)
    return {"cancelled": cancel_job(j.id)}


@router.get("/{job_id}/events")
async def events(job_id: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _owned(db, user, job_id)

    async def gen():
        last = None
        while True:
            if await request.is_disconnected():
                break
            with SessionLocal() as s:
                j = s.get(Job, job_id)
                payload = job_dict(j) if j else None
            if payload is None:
                yield {"event": "gone", "data": "{}"}
                break
            key = (payload["status"], payload["progress"], payload["message"])
            if key != last:
                last = key
                yield {"event": "job", "data": json.dumps(payload)}
            if payload["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.6)

    return EventSourceResponse(gen())
