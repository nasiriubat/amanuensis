from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_admin
from ..models import LlmCall, Project, iso
from ..schemas import UsageRow, UsageSummary

router = APIRouter(prefix="/api/usage", tags=["usage"], dependencies=[Depends(require_admin)])

_AGG = (
    func.count(LlmCall.id),
    func.coalesce(func.sum(LlmCall.input_tokens), 0),
    func.coalesce(func.sum(LlmCall.output_tokens), 0),
    func.coalesce(func.sum(LlmCall.cached_tokens), 0),
    func.coalesce(func.sum(case((LlmCall.ok.is_(False), 1), else_=0)), 0),
)


def _to_rows(result) -> list[UsageRow]:
    return [
        UsageRow(
            key=str(r[0] or "none"),
            label=str(r[1] or "unassigned"),
            calls=r[2],
            input_tokens=r[3],
            output_tokens=r[4],
            cached_tokens=r[5],
            errors=r[6],
        )
        for r in result
    ]


def _grouped(db: Session, key_col, label_col) -> list[UsageRow]:
    q = (
        select(key_col, label_col, *_AGG)
        .group_by(key_col, label_col)
        .order_by(func.sum(LlmCall.input_tokens + LlmCall.output_tokens).desc())
    )
    return _to_rows(db.execute(q).all())


def _by_project(db: Session) -> list[UsageRow]:
    q = (
        select(LlmCall.project_id, Project.title, *_AGG)
        .join(Project, Project.id == LlmCall.project_id, isouter=True)
        .group_by(LlmCall.project_id, Project.title)
        .order_by(func.sum(LlmCall.input_tokens + LlmCall.output_tokens).desc())
    )
    return _to_rows(db.execute(q).all())


@router.get("/summary", response_model=UsageSummary)
def summary(db: Session = Depends(get_db)):
    totals = db.execute(
        select(
            func.count(LlmCall.id),
            func.coalesce(func.sum(LlmCall.input_tokens), 0),
            func.coalesce(func.sum(LlmCall.output_tokens), 0),
        )
    ).one()
    recent = db.scalars(select(LlmCall).order_by(LlmCall.created_at.desc()).limit(25)).all()
    return UsageSummary(
        total_calls=totals[0],
        total_input_tokens=totals[1],
        total_output_tokens=totals[2],
        by_provider=_grouped(db, LlmCall.provider_id, LlmCall.provider_name),
        by_purpose=_grouped(db, LlmCall.purpose, LlmCall.purpose),
        by_project=_by_project(db),
        recent=[
            {
                "id": c.id,
                "purpose": c.purpose,
                "provider": c.provider_name,
                "model": c.model,
                "input_tokens": c.input_tokens,
                "output_tokens": c.output_tokens,
                "cached_tokens": c.cached_tokens,
                "duration_ms": c.duration_ms,
                "ok": c.ok,
                "error": c.error,
                "created_at": iso(c.created_at),
            }
            for c in recent
        ],
    )
