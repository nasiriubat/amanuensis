"""Background reading (ROADMAP day 9): the papers an author read for the study.

A reading is ingested like an exemplar (full text under `readings/<id>/`) but never feeds the
playbook. Instead one utility call writes a *reading card*: question, method, result,
limitation, relation to the author's work, and what the paper can be cited for. The card is
attached to the paper's reference record, so the paper is citable at once and drafting may
attribute to it what the card says rather than only its abstract.
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import storage
from ..db import SessionLocal
from ..ingest import extract as ingest_extract
from ..ingest import service as ingest
from ..jobs import JobContext
from ..kinds import kind_exists, kind_name
from ..learn.context import budget_markdown, render
from ..llm.base import Message
from ..llm.jsonio import extract_json
from ..llm.registry import complete
from ..models import Project
from . import scan
from . import service as refs

DIR = "readings"
CARD_KEYS = ("question", "method", "result", "limitation", "relation", "cite_for")
CARD_MAX_CHARS = 36_000


def readings_dir(root: Path) -> Path:
    return root / DIR


def load_card(folder: Path) -> dict | None:
    p = folder / "card.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def list_readings(root: Path) -> list[dict]:
    out = []
    for meta in ingest.list_papers(readings_dir(root)):
        folder = readings_dir(root) / meta["id"]
        card = load_card(folder)
        meta["card"] = card
        meta["ref_key"] = (card or {}).get("ref_key")
        out.append(meta)
    return out


def cards(root: Path) -> list[dict]:
    """Reference records that carry a reading card, for drafting."""
    return [r for r in refs.list_records(root) if r.get("card")]


def _clean(card: dict) -> dict:
    return {k: str(card.get(k, "") or "").strip()[:900] for k in CARD_KEYS}


def attach_card(root: Path, meta: dict, card: dict, reading_id: str) -> str:
    """Create or update the reference record for this paper and store the card on it."""
    cand = scan.candidate_from_meta(meta)
    cand["source"] = "reading"
    key = scan.existing_key_for(root, cand)
    record = refs.get_record(root, key) if key else None
    if not record:
        record = refs.accept(root, cand)
        key = record["key"]
    record["card"] = card
    record["reading_id"] = reading_id
    if not record.get("abstract") and meta.get("abstract"):
        record["abstract"] = meta["abstract"]
    refs._save(root, record)
    return key


async def summarise_reading(project_id: str, paper_id: str, ctx: JobContext | None = None) -> dict:
    """Write the reading card for one ingested paper and attach it to its reference."""
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if not project:
            raise ValueError("Project not found")
        db.expunge(project)
    root = storage.project_dir(project.slug)
    folder = readings_dir(root) / paper_id
    meta = ingest_extract.read_meta(folder) if folder.is_dir() else None
    if not meta or meta.get("status") != "ready":
        raise ValueError("The paper is not extracted yet")
    md = storage.read_text(folder / "extracted.md")
    if not md.strip():
        raise ValueError("No text was extracted from this paper")
    kname = kind_name(project.kind) if kind_exists(project.kind) else project.kind
    if ctx:
        ctx.progress(70, f"Writing the reading card for “{meta.get('title', paper_id)[:60]}”")
    prompt = render(
        "reading_card.j2",
        kind_name=kname,
        title=project.title,
        spec=budget_markdown(storage.read_text(root / "inputs" / "system-spec.md"), 4000),
        paper_title=meta.get("title", paper_id),
        paper=budget_markdown(md, CARD_MAX_CHARS),
    )
    with SessionLocal() as db:
        p = db.get(Project, project_id)
        result = await complete(
            db,
            "utility",
            [Message("user", prompt)],
            project=p,
            user_id=ctx.user_id if ctx else None,
            max_tokens=900,
            temperature=0.1,
            json_mode=True,
        )
    card = _clean(extract_json(result.text))
    card["tokens_in"] = result.usage.input_tokens
    card["tokens_out"] = result.usage.output_tokens
    key = attach_card(root, meta, card, paper_id)
    card["ref_key"] = key
    storage.write_text(folder / "card.json", json.dumps(card, indent=2, ensure_ascii=False))
    storage.git_commit(root, f"Reading card: {key}")
    if ctx:
        ctx.progress(100, f"Read “{meta.get('title', '')[:60]}”, citable as [@{key}]")
    return card


async def ingest_reading(
    project_id: str,
    ctx: JobContext,
    *,
    arxiv_id: str | None = None,
    pdf_bytes: bytes | None = None,
    filename: str = "paper.pdf",
    pdf_url: str | None = None,
    title: str = "",
) -> dict:
    """Ingest one paper into readings/ and write its card in the same job."""
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if not project:
            raise ValueError("Project not found")
        slug = project.slug
    root = storage.project_dir(slug)
    target = readings_dir(root)
    if arxiv_id:
        res = await ingest.ingest_arxiv(target, arxiv_id, ctx)
    elif pdf_bytes is not None:
        res = await ingest.ingest_pdf(target, pdf_bytes, filename, ctx)
    elif pdf_url:
        res = await ingest.ingest_pdf_url(target, pdf_url, ctx, title)
    else:
        raise ValueError("Nothing to ingest")
    card = await summarise_reading(project_id, res["id"], ctx)
    return {
        **res,
        "ref_key": card.get("ref_key"),
        "tokens_in": card.get("tokens_in"),
        "tokens_out": card.get("tokens_out"),
    }


def delete_reading(root: Path, paper_id: str) -> bool:
    """Remove the paper's text. Its reference record and card stay: the author did read it."""
    return ingest.delete_paper(readings_dir(root), paper_id)


def card_lines(record: dict, full: bool = False) -> str:
    """One card as prompt text. `full` for related-work sections, short elsewhere."""
    c = record.get("card") or {}
    if full:
        parts = [
            f"question: {c.get('question', '')}",
            f"method: {c.get('method', '')}",
            f"result: {c.get('result', '')}",
        ]
        if c.get("limitation") and c["limitation"].lower() != "not stated":
            parts.append(f"limitation: {c['limitation']}")
        if c.get("relation"):
            parts.append(f"relation to this paper: {c['relation']}")
        if c.get("cite_for"):
            parts.append(f"cite for: {c['cite_for']}")
        return "\n    ".join(parts)
    return f"{c.get('question', '')} {c.get('result', '')}".strip()[:600]
