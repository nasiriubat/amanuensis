"""Admin view of disk use and safe, explicit cleanup actions (SPEC 6: keep the box small)."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from .. import storage
from ..config import get_settings
from ..db import get_db
from ..deps import require_admin
from ..models import AuthorProfile, AuthSession, Job, LlmCall, Project, iso, now

router = APIRouter(prefix="/api/admin/storage", tags=["maintenance"], dependencies=[Depends(require_admin)])


def dir_size(path: Path) -> int:
    """Bytes under a directory, or the size of a single file."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    stack = [path]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _db_bytes() -> int:
    data = get_settings().data_dir
    return sum(dir_size(data / n) for n in ("app.db", "app.db-wal", "app.db-shm"))


def _project_breakdown(root: Path) -> dict:
    parts = {
        "exemplars": dir_size(root / "exemplars"),
        "exports": dir_size(root / "exports"),
        "figures": dir_size(root / "figures"),
        "history": dir_size(root / ".git"),
    }
    total = dir_size(root)
    parts["other"] = max(0, total - sum(parts.values()))
    return {"total": total, **parts}


def _profile_breakdown(root: Path) -> dict:
    parts = {"sources": dir_size(root / "sources"), "history": dir_size(root / ".git")}
    total = dir_size(root)
    parts["other"] = max(0, total - sum(parts.values()))
    return {"total": total, **parts}


def _raw_source_paths(paper_dir: Path) -> list[Path]:
    """Files that were only needed for extraction: LaTeX source trees and the original PDF."""
    out = []
    for name in ("src", "source.pdf", "source.tar", "source.tar.gz"):
        p = paper_dir / name
        if p.exists():
            out.append(p)
    return out


@router.get("")
def overview(db: Session = Depends(get_db)):
    data = get_settings().data_dir
    projects = []
    for p in db.scalars(select(Project).order_by(Project.title)).all():
        root = storage.project_dir(p.slug)
        b = _project_breakdown(root)
        projects.append(
            {
                "slug": p.slug,
                "title": p.title,
                "owner_id": p.owner_id,
                "exports_count": len(list((root / "exports").glob("*"))) if (root / "exports").exists() else 0,
                **b,
            }
        )
    profiles = []
    for pr in db.scalars(select(AuthorProfile).order_by(AuthorProfile.name)).all():
        root = storage.profile_dir(pr.slug)
        profiles.append({"slug": pr.slug, "name": pr.name, **_profile_breakdown(root)})
    raw_bytes = 0
    for group in (data / "projects", data / "profiles"):
        if not group.exists():
            continue
        for sub in ("exemplars", "sources"):
            for paper in group.glob(f"*/{sub}/*"):
                if paper.is_dir():
                    raw_bytes += sum(dir_size(x) for x in _raw_source_paths(paper))
    ts = now()
    counts = {
        "llm_calls": db.scalar(select(func.count(LlmCall.id))) or 0,
        "llm_calls_old": db.scalar(select(func.count(LlmCall.id)).where(LlmCall.created_at < ts - timedelta(days=90)))
        or 0,
        "jobs": db.scalar(select(func.count(Job.id))) or 0,
        "jobs_finished": db.scalar(select(func.count(Job.id)).where(Job.status.in_(["done", "failed"]))) or 0,
        "sessions": db.scalar(select(func.count(AuthSession.id))) or 0,
        "sessions_expired": db.scalar(select(func.count(AuthSession.id)).where(AuthSession.expires_at < ts)) or 0,
    }
    oldest = db.scalar(select(func.min(LlmCall.created_at)))
    projects_total = sum(p["total"] for p in projects)
    profiles_total = sum(p["total"] for p in profiles)
    other = {
        "database": _db_bytes(),
        "templates": dir_size(data / "templates"),
        "kinds": dir_size(data / "kinds"),
        "branding": dir_size(data / "branding"),
    }
    free = shutil.disk_usage(data).free if data.exists() else None
    return {
        "data_dir": str(data),
        "total": projects_total + profiles_total + sum(other.values()),
        "projects_total": projects_total,
        "profiles_total": profiles_total,
        "raw_sources": raw_bytes,
        "exports_total": sum(p["exports"] for p in projects),
        "history_total": sum(p["history"] for p in projects) + sum(p["history"] for p in profiles),
        "disk_free": free,
        "other": other,
        "projects": sorted(projects, key=lambda x: -x["total"]),
        "profiles": sorted(profiles, key=lambda x: -x["total"]),
        "counts": counts,
        "oldest_llm_call": iso(oldest) if oldest else None,
        "checked_at": iso(ts),
    }


ACTIONS = ("exports", "raw_sources", "history", "jobs", "llm_calls", "sessions", "vacuum")


class CleanupIn(BaseModel):
    actions: list[str] = Field(min_length=1, max_length=len(ACTIONS))
    keep_exports: int = Field(default=3, ge=0, le=50)
    older_than_days: int = Field(default=90, ge=0, le=3650)
    project_slug: str | None = Field(default=None, max_length=120)


def _prune_exports(root: Path, keep: int) -> tuple[int, int]:
    d = root / "exports"
    if not d.exists():
        return 0, 0
    stamps = sorted([x for x in d.iterdir() if x.is_dir()], key=lambda x: x.name, reverse=True)
    freed = removed = 0
    for old in stamps[keep:]:
        freed += dir_size(old)
        shutil.rmtree(old, ignore_errors=True)
        removed += 1
    return removed, freed


def _drop_raw_sources(root: Path, sub: str) -> tuple[int, int]:
    group = root / sub
    if not group.exists():
        return 0, 0
    freed = removed = 0
    for paper in group.iterdir():
        if not paper.is_dir() or not (paper / "extracted.md").exists():
            continue  # never drop sources of a paper that has not been extracted yet
        for p in _raw_source_paths(paper):
            freed += dir_size(p)
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
            removed += 1
    return removed, freed


def _git_gc(root: Path) -> int:
    if not (root / ".git").exists():
        return 0
    before = dir_size(root / ".git")
    try:
        subprocess.run(
            ["git", "-C", str(root), "gc", "--prune=now", "--quiet"],
            check=False,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0
    return max(0, before - dir_size(root / ".git"))


@router.post("/cleanup")
def cleanup(body: CleanupIn, db: Session = Depends(get_db)):
    unknown = [a for a in body.actions if a not in ACTIONS]
    if unknown:
        raise ValueError(f"Unknown cleanup action: {', '.join(unknown)}")
    ts = now()
    cutoff = ts - timedelta(days=body.older_than_days)
    report: dict[str, dict] = {}

    projects = db.scalars(select(Project)).all()
    profiles = db.scalars(select(AuthorProfile)).all()
    if body.project_slug:
        projects = [p for p in projects if p.slug == body.project_slug]
        profiles = []

    if "exports" in body.actions:
        removed = freed = 0
        for p in projects:
            r, f = _prune_exports(storage.project_dir(p.slug), body.keep_exports)
            removed += r
            freed += f
        report["exports"] = {"removed": removed, "freed": freed}

    if "raw_sources" in body.actions:
        removed = freed = 0
        for p in projects:
            r, f = _drop_raw_sources(storage.project_dir(p.slug), "exemplars")
            removed += r
            freed += f
        for pr in profiles:
            r, f = _drop_raw_sources(storage.profile_dir(pr.slug), "sources")
            removed += r
            freed += f
        report["raw_sources"] = {"removed": removed, "freed": freed}

    if "history" in body.actions:
        freed = 0
        for p in projects:
            freed += _git_gc(storage.project_dir(p.slug))
        for pr in profiles:
            freed += _git_gc(storage.profile_dir(pr.slug))
        report["history"] = {"freed": freed}

    if "jobs" in body.actions:
        q = delete(Job).where(Job.status.in_(["done", "failed"]), Job.updated_at < cutoff)
        if body.project_slug:
            ids = [p.id for p in projects]
            q = q.where(Job.project_id.in_(ids))
        res = db.execute(q.execution_options(synchronize_session=False))
        db.commit()
        report["jobs"] = {"removed": res.rowcount or 0}

    if "llm_calls" in body.actions:
        q = delete(LlmCall).where(LlmCall.created_at < cutoff)
        if body.project_slug:
            q = q.where(LlmCall.project_id.in_([p.id for p in projects]))
        res = db.execute(q.execution_options(synchronize_session=False))
        db.commit()
        report["llm_calls"] = {"removed": res.rowcount or 0}

    if "sessions" in body.actions:
        res = db.execute(
            delete(AuthSession).where(AuthSession.expires_at < ts).execution_options(synchronize_session=False)
        )
        db.commit()
        report["sessions"] = {"removed": res.rowcount or 0}

    if "vacuum" in body.actions:
        before = _db_bytes()
        db.commit()
        with db.get_bind().connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            conn.execute(text("VACUUM"))
        report["vacuum"] = {"freed": max(0, before - _db_bytes())}

    freed = sum(int(v.get("freed", 0)) for v in report.values())
    return {"report": report, "freed": freed, "finished_at": iso(now())}


BACKUP_SKIP_DIRS = {".git"}


def _backup_zip(include_exports: bool, include_raw: bool) -> Path:
    """Consistent snapshot of the data volume: SQLite via its backup API, files by walking."""
    import sqlite3
    import tempfile
    import zipfile

    settings = get_settings()
    data = settings.data_dir.resolve()
    tmpdir = Path(tempfile.mkdtemp(prefix="pw-backup-"))
    stamp = now().strftime("%Y%m%d-%H%M%S")
    out = tmpdir / f"coscribe-backup-{stamp}.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        db_snapshot = tmpdir / "app.db"
        src = sqlite3.connect(str(settings.db_path))
        try:
            dst = sqlite3.connect(str(db_snapshot))
            with dst:
                src.backup(dst)
            dst.close()
        finally:
            src.close()
        zf.write(db_snapshot, "app.db")
        db_snapshot.unlink()
        for path in sorted(data.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(data)
            parts = rel.parts
            if parts[0] in ("app.db", "app.db-wal", "app.db-shm", "tmp"):
                continue
            if BACKUP_SKIP_DIRS & set(parts[:-1]):
                continue  # git history is a convenience cache; drafts and versions of files are on disk
            if not include_exports and "exports" in parts:
                continue
            if not include_raw and ("src" in parts or path.name in ("source.pdf", "source.tar", "source.tar.gz")):
                continue
            zf.write(path, str(rel))
        zf.writestr(
            "RESTORE.txt",
            "Restore: stop the container, empty the data volume, unzip this archive into it, start again.\n"
            "The database is a consistent snapshot taken with SQLite's backup API. Git history was not\n"
            "included; every file is present at its latest version and history restarts from there.\n",
        )
    return out


@router.get("/backup")
def backup(include_exports: bool = True, include_raw: bool = False):
    from fastapi.responses import FileResponse
    from starlette.background import BackgroundTask

    out = _backup_zip(include_exports, include_raw)

    def _cleanup(p: Path = out) -> None:
        shutil.rmtree(p.parent, ignore_errors=True)

    return FileResponse(
        out,
        media_type="application/zip",
        filename=out.name,
        headers={"Cache-Control": "no-store"},
        background=BackgroundTask(_cleanup),
    )


def purge_expired_sessions() -> int:
    """Called at boot so the sessions table never grows without bound."""
    from ..db import SessionLocal

    with SessionLocal() as db:
        res = db.execute(
            delete(AuthSession).where(AuthSession.expires_at < now()).execution_options(synchronize_session=False)
        )
        db.commit()
        return res.rowcount or 0
