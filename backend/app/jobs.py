"""In-process background jobs with progress rows in SQLite.

A job is an async function taking a JobContext. It runs as an asyncio task in the
server process. Progress is written to the jobs table so the UI can poll or stream it.
No external queue in v1 (see SPEC 3.3).
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Job, now

log = logging.getLogger("amanuensis.jobs")

_tasks: dict[str, asyncio.Task] = {}


@dataclass
class JobContext:
    job_id: str
    user_id: str

    def progress(self, pct: int, message: str | None = None) -> None:
        with SessionLocal() as db:
            job = db.get(Job, self.job_id)
            if job:
                job.progress = max(0, min(100, int(pct)))
                if message is not None:
                    job.message = message[:2000]
                job.updated_at = now()
                db.commit()

    def result(self, data: dict) -> None:
        with SessionLocal() as db:
            job = db.get(Job, self.job_id)
            if job:
                job.result = data
                db.commit()


def create_job(
    db: Session,
    *,
    user_id: str,
    type: str,
    project_id: str | None = None,
    profile_id: str | None = None,
    message: str | None = None,
) -> Job:
    job = Job(
        user_id=user_id, type=type, project_id=project_id, profile_id=profile_id, message=message, status="queued"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def start_job(job: Job, fn: Callable[[JobContext], Awaitable[dict | None]]) -> None:
    ctx = JobContext(job_id=job.id, user_id=job.user_id)

    async def runner():
        with SessionLocal() as db:
            j = db.get(Job, job.id)
            if j:
                j.status = "running"
                j.updated_at = now()
                db.commit()
        try:
            result = await fn(ctx)
            with SessionLocal() as db:
                j = db.get(Job, job.id)
                if j:
                    j.status = "done"
                    j.progress = 100
                    if result is not None:
                        j.result = result
                    j.updated_at = now()
                    db.commit()
        except asyncio.CancelledError:
            with SessionLocal() as db:
                j = db.get(Job, job.id)
                if j:
                    j.status = "failed"
                    j.error = "Cancelled"
                    j.updated_at = now()
                    db.commit()
            raise
        except Exception as e:
            log.error("job %s failed: %s\n%s", job.id, e, traceback.format_exc())
            with SessionLocal() as db:
                j = db.get(Job, job.id)
                if j:
                    j.status = "failed"
                    j.error = f"{type(e).__name__}: {e}"[:4000]
                    j.updated_at = now()
                    db.commit()
        finally:
            _tasks.pop(job.id, None)

    _tasks[job.id] = asyncio.create_task(runner())


def cancel_job(job_id: str) -> bool:
    t = _tasks.get(job_id)
    if t and not t.done():
        t.cancel()
        return True
    return False


def job_dict(j: Job) -> dict:
    from .models import iso

    return {
        "id": j.id,
        "type": j.type,
        "status": j.status,
        "progress": j.progress,
        "message": j.message,
        "error": j.error,
        "result": j.result,
        "project_id": j.project_id,
        "profile_id": j.profile_id,
        "created_at": iso(j.created_at),
        "updated_at": iso(j.updated_at),
    }
