"""User study kit (ROADMAP item 10): opt-in usage events, a per-project summary, CSV export,
the study documents, and a one-click participant guide page.

Events record which page or action and when. They never record text. Recording is off until
an admin switches it on, and the public site payload tells the frontend so it can stay silent.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from itertools import pairwise

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import storage
from ..config import get_settings
from ..db import get_db
from ..deps import current_user, require_admin
from ..models import Event, LlmCall, Page, Project, SiteSetting, User, iso, now
from .projects import _counts
from .site import _unique_slug, study_enabled

router = APIRouter(prefix="/api", tags=["study"])

KINDS = {
    "page",
    "section_saved",
    "section_drafted",
    "fix_accepted",
    "fix_discarded",
    "section_added",
    "export_downloaded",
    "critique_run",
    "scan_run",
    "reference_added",
}
STEP_RE = re.compile(r"^/projects/[^/]+/?([a-z-]*)")
SESSION_GAP_S = 30 * 60
KIT_FILES = ("participant-guide.md", "consent.md", "questionnaire.md", "interview-guide.md")


class EventIn(BaseModel):
    kind: str = Field(min_length=1, max_length=48)
    project_slug: str | None = Field(default=None, max_length=120)
    path: str | None = Field(default=None, max_length=255)
    meta: dict | None = None


class StudyIn(BaseModel):
    enabled: bool


def _study_row(db: Session) -> SiteSetting:
    row = db.get(SiteSetting, "study")
    if not row:
        row = SiteSetting(key="study", value={"enabled": False})
        db.add(row)
        db.commit()
    return row


# ------------------------------------------------------------------ recording


@router.post("/events", status_code=204)
def record_event(body: EventIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not study_enabled(db) or body.kind not in KINDS:
        return Response(status_code=204)
    project_id = None
    if body.project_slug:
        project_id = db.scalar(select(Project.id).where(Project.slug == body.project_slug))
    meta = body.meta or {}
    # keep it small and text-free: numbers, booleans and short labels only
    meta = {k: v for k, v in meta.items() if isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) <= 64)}
    db.add(
        Event(user_id=user.id, project_id=project_id, kind=body.kind, path=(body.path or "")[:255] or None, meta=meta)
    )
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------------ admin


@router.get("/admin/study")
def get_study(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = _study_row(db)
    return {
        "enabled": bool(row.value and row.value.get("enabled")),
        "since": (row.value or {}).get("since"),
        "events": db.scalar(select(func.count(Event.id))) or 0,
        "projects": summary(db),
    }


@router.put("/admin/study")
def put_study(body: StudyIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = _study_row(db)
    value = dict(row.value or {})
    value["enabled"] = body.enabled
    if body.enabled and not value.get("since"):
        value["since"] = iso(now())
    row.value = value
    db.commit()
    return {"enabled": body.enabled, "since": value.get("since")}


def _step_of(path: str | None) -> str:
    if not path:
        return "other"
    m = STEP_RE.match(path)
    if not m:
        return "other"
    return m.group(1) or "home"


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _minutes_by_step(events: list[Event]) -> tuple[dict[str, float], float]:
    """Attribute the gap between consecutive events to the step of the earlier one, capped by
    the session gap so an open tab overnight does not count."""
    by_step: dict[str, float] = defaultdict(float)
    total = 0.0
    ordered = sorted(events, key=lambda e: e.created_at)
    for a, b in pairwise(ordered):
        gap = (_as_utc(b.created_at) - _as_utc(a.created_at)).total_seconds()
        if 0 < gap <= SESSION_GAP_S:
            by_step[_step_of(a.path)] += gap / 60
            total += gap / 60
    return {k: round(v, 1) for k, v in by_step.items()}, round(total, 1)


def _verdicts(root) -> list[str]:
    p = root / "review.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    history = data.get("history") or [data]
    return [str(h.get("verdict", "")) for h in history if h.get("verdict")]


def _section_statuses(root) -> dict[str, int]:
    p = root / "sections" / "index.json"
    out: dict[str, int] = defaultdict(int)
    if p.exists():
        try:
            for s in json.loads(p.read_text(encoding="utf-8")).get("sections", []):
                out[s.get("status", "empty")] += 1
        except json.JSONDecodeError:
            pass
    return dict(out)


def summary(db: Session) -> list[dict]:
    projects = db.scalars(select(Project).order_by(Project.created_at)).all()
    owners = {u.id: u for u in db.scalars(select(User)).all()}
    events_by_project: dict[str, list[Event]] = defaultdict(list)
    for e in db.scalars(select(Event)).all():
        if e.project_id:
            events_by_project[e.project_id].append(e)
    tokens = db.execute(
        select(
            LlmCall.project_id,
            LlmCall.purpose,
            func.count(LlmCall.id),
            func.coalesce(func.sum(LlmCall.input_tokens + LlmCall.output_tokens), 0),
        ).group_by(LlmCall.project_id, LlmCall.purpose)
    ).all()
    tok_by_project: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    for pid, purpose, calls, total in tokens:
        if pid:
            tok_by_project[pid][purpose] = {"calls": calls, "tokens": int(total)}
    rows = []
    for p in projects:
        root = storage.project_dir(p.slug)
        evs = events_by_project.get(p.id, [])
        by_step, minutes = _minutes_by_step(evs)
        counts = _counts(p.slug)
        kinds: dict[str, int] = defaultdict(int)
        for e in evs:
            kinds[e.kind] += 1
        owner = owners.get(p.owner_id)
        rows.append(
            {
                "slug": p.slug,
                "title": p.title,
                "kind": p.kind,
                "entry": p.entry,
                "owner": owner.display_name if owner else None,
                "created_at": iso(p.created_at),
                "events": len(evs),
                "event_kinds": dict(kinds),
                "active_minutes": minutes,
                "minutes_by_step": by_step,
                "first_event": iso(min(e.created_at for e in evs)) if evs else None,
                "last_event": iso(max(e.created_at for e in evs)) if evs else None,
                "tokens_by_purpose": tok_by_project.get(p.id, {}),
                "tokens_total": sum(v["tokens"] for v in tok_by_project.get(p.id, {}).values()),
                "sections": _section_statuses(root),
                "exports": counts["exports"],
                "references": counts["references"],
                "cite_requests": counts["cite_requests"],
                "verdicts": _verdicts(root),
            }
        )
    return rows


@router.get("/admin/study/events.csv")
def events_csv(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = {u.id: u.email for u in db.scalars(select(User)).all()}
    projects = {p.id: p.slug for p in db.scalars(select(Project)).all()}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["at", "user", "project", "kind", "step", "path", "meta"])
    for e in db.scalars(select(Event).order_by(Event.created_at)).all():
        w.writerow(
            [
                iso(e.created_at),
                users.get(e.user_id or "", ""),
                projects.get(e.project_id or "", ""),
                e.kind,
                _step_of(e.path),
                e.path or "",
                json.dumps(e.meta or {}, ensure_ascii=False),
            ]
        )
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="coscribe-events.csv"'},
    )


@router.get("/admin/study/summary.json")
def summary_json(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return Response(
        json.dumps(summary(db), indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="coscribe-study-summary.json"'},
    )


@router.delete("/admin/study/events", status_code=204)
def delete_events(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Erase every recorded event, for example when a participant withdraws after the study."""
    for e in db.scalars(select(Event)).all():
        db.delete(e)
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------------ kit documents


def _kit_dir():
    return get_settings().seed_dir / "study"


@router.get("/admin/study/kit")
def kit(_: User = Depends(require_admin)):
    out = []
    for name in KIT_FILES:
        p = _kit_dir() / name
        if p.exists():
            text = p.read_text(encoding="utf-8")
            title = text.splitlines()[0].lstrip("# ").strip() if text else name
            out.append({"name": name, "title": title, "content": text})
    return out


@router.post("/admin/study/guide-page", status_code=201)
def create_guide_page(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Create the participant guide as an unpublished page the admin can edit and publish."""
    existing = db.scalar(select(Page).where(Page.slug.like("participant-guide%")))
    if existing:
        return {"id": existing.id, "slug": existing.slug, "created": False}
    p = _kit_dir() / "participant-guide.md"
    if not p.exists():
        raise HTTPException(404, "The participant guide is missing from the seed folder")
    page = Page(
        slug=_unique_slug(db, "participant-guide"),
        title="Participant guide",
        content=p.read_text(encoding="utf-8"),
        published=False,
        show_in_nav=False,
        nav_order=9,
    )
    db.add(page)
    db.commit()
    return {"id": page.id, "slug": page.slug, "created": True}
