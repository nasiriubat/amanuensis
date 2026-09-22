from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import storage
from ..db import get_db
from ..deps import current_user
from ..interview import service as svc
from ..jobs import create_job, job_dict, start_job
from ..llm.base import LLMError
from ..models import User
from ..security import llm_limiter
from .projects import get_owned

router = APIRouter(prefix="/api/projects/{slug}", tags=["interview"])


class AnswerIn(BaseModel):
    id: str
    answer: str | None = Field(default=None, max_length=8000)
    status: Literal["open", "answered", "na"] | None = None


class AnswersIn(BaseModel):
    answers: list[AnswerIn] = Field(max_length=100)


class PinIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class PlanIn(BaseModel):
    mode: Literal["refine", "explore"] = "refine"


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=6000)


def _limit(user: User) -> None:
    if not llm_limiter.allow(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down")


# ------------------------------------------------------------------ interview


@router.get("/interview")
def get_interview(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    return svc.load_interview(storage.project_dir(p.slug))


@router.post("/interview/next", status_code=202)
async def next_round(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    _limit(user)
    job = create_job(db, user_id=user.id, type="interview_round", project_id=p.id, message="Queued")
    start_job(job, lambda ctx: svc.generate_round(p.id, ctx))
    return job_dict(job)


@router.put("/interview/answers")
def put_answers(slug: str, body: AnswersIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    return svc.apply_answers(storage.project_dir(p.slug), [a.model_dump() for a in body.answers])


@router.post("/interview/pin")
def pin(slug: str, body: PinIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    return svc.pin_note(storage.project_dir(p.slug), body.text)


# ------------------------------------------------------------------ research plan


@router.post("/design/generate", status_code=202)
async def generate_plan(slug: str, body: PlanIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    _limit(user)
    if not storage.read_text(storage.project_dir(p.slug) / "inputs" / "idea.md").strip():
        raise HTTPException(400, "Write your idea first")
    job = create_job(db, user_id=user.id, type="research_plan", project_id=p.id, message="Queued")
    start_job(job, lambda ctx: svc.generate_plan(p.id, ctx, mode=body.mode))
    return job_dict(job)


# ------------------------------------------------------------------ outline


@router.post("/outline/generate", status_code=202)
async def generate_outline(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    _limit(user)
    if not storage.read_text(storage.project_dir(p.slug) / "inputs" / "system-spec.md").strip():
        raise HTTPException(400, "Write the system specification first")
    job = create_job(db, user_id=user.id, type="outline", project_id=p.id, message="Queued")
    start_job(job, lambda ctx: svc.generate_outline(p.id, ctx))
    return job_dict(job)


@router.post("/outline/approve")
def approve_outline(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    if not storage.read_text(storage.project_dir(p.slug) / "outline.md").strip():
        raise HTTPException(400, "There is no outline to approve")
    p.stage = "outline"
    db.commit()
    storage.git_commit(storage.project_dir(p.slug), "Outline approved")
    return {"stage": p.stage}


# ------------------------------------------------------------------ side chat


@router.get("/chat")
def get_chat(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    return svc.load_chat(storage.project_dir(p.slug))


@router.post("/chat")
async def post_chat(slug: str, body: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    _limit(user)
    try:
        return await svc.chat_reply(p.id, user.id, body.message)
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e


@router.delete("/chat", status_code=204)
def clear_chat(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = get_owned(db, user, slug)
    svc.save_chat(storage.project_dir(p.slug), [])
