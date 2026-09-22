from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from . import storage
from .config import get_settings
from .db import SessionLocal, init_db
from .models import User
from .routers import (
    auth,
    interview,
    jobs,
    kinds,
    papers,
    profiles,
    projects,
    providers,
    references,
    studio,
    usage,
    users,
)
from .security import hash_password

log = logging.getLogger("paper-writer")


def seed_admin() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)):
            return
        admin = User(
            email=settings.admin_email.lower(),
            display_name="Admin",
            password_hash=hash_password(settings.admin_password),
            role="admin",
            must_change_password=True,
        )
        db.add(admin)
        db.commit()
        log.info("Seeded first admin account %s", admin.email)


def fail_orphaned_jobs() -> None:
    """Jobs run in-process; anything still queued or running at boot died with the previous process."""
    from .models import Job, now

    with SessionLocal() as db:
        stale = db.scalars(select(Job).where(Job.status.in_(["queued", "running"]))).all()
        for j in stale:
            j.status = "failed"
            j.error = "Server restarted before this job finished"
            j.updated_at = now()
        if stale:
            db.commit()
            log.info("Marked %d orphaned jobs as failed", len(stale))


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    storage.seed_defaults()
    seed_admin()
    fail_orphaned_jobs()
    yield


app = FastAPI(
    title="Paper Writer", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json"
)

for r in (auth, users, providers, profiles, projects, papers, interview, studio, references, kinds, usage, jobs):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"ok": True, "version": app.version}


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ---------------------------------------------------------------- SPA serving (production)

_dist = (Path(__file__).resolve().parent.parent / get_settings().frontend_dist).resolve()
if _dist.is_dir() and (_dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        candidate = (_dist / full_path).resolve()
        if full_path and candidate.is_file() and _dist in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
