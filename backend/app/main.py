from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from . import storage
from .config import get_settings
from .db import SessionLocal, init_db
from .models import User
from .routers import (
    auth,
    export,
    figures,
    interview,
    jobs,
    kinds,
    maintenance,
    papers,
    profiles,
    projects,
    providers,
    references,
    review,
    site,
    studio,
    usage,
    users,
)
from .security import hash_password

log = logging.getLogger("paper-writer")

# Largest single upload the API accepts (exemplar PDFs are capped at 40 MB by their route).
MAX_REQUEST_BYTES = 45 * 1024 * 1024

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


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
    from .export.service import seed_templates

    seed_templates()
    with SessionLocal() as db:
        site.seed_pages(db)
    purged = maintenance.purge_expired_sessions()
    if purged:
        log.info("Purged %d expired sessions", purged)
    yield


app = FastAPI(
    title="Paper Writer", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json"
)


@app.middleware("http")
async def hardening(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_REQUEST_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Request body too large"})
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


for r in (
    auth,
    users,
    providers,
    profiles,
    projects,
    papers,
    interview,
    studio,
    references,
    kinds,
    usage,
    jobs,
    site,
    figures,
    export,
    review,
    maintenance,
):
    app.include_router(r.router)
app.include_router(site.robots_router)


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
    _index_cache: dict = {"mtime": 0.0, "html": ""}

    def _index_html() -> str:
        # Re-read when the frontend is rebuilt under a running dev server; a stat per request is cheap.
        path = _dist / "index.html"
        mtime = path.stat().st_mtime
        if mtime != _index_cache["mtime"]:
            _index_cache.update(mtime=mtime, html=path.read_text(encoding="utf-8"))
        return _index_cache["html"]

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        candidate = (_dist / full_path).resolve()
        if full_path and candidate.is_file() and _dist in candidate.parents:
            return FileResponse(candidate)
        # Crawlers and link previews read the head before any script runs, so it is rendered here.
        from .seo import head_for, inject

        with SessionLocal() as db:
            meta = head_for(full_path, site.load_site(db), db)
        return HTMLResponse(inject(_index_html(), meta), headers={"Cache-Control": "no-cache"})
