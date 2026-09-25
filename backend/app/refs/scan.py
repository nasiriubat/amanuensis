"""Literature scan: from the author's idea, plan and spec to a ranked list of papers to cite or learn from.

Nothing here writes a reference on its own. The scan proposes; the author adopts.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from .. import storage
from ..db import SessionLocal
from ..ingest import extract as ingest_extract
from ..jobs import JobContext
from ..kinds import kind_exists, kind_name
from ..learn.context import budget_markdown, render
from ..llm.base import Message
from ..llm.jsonio import extract_json
from ..llm.registry import complete
from ..models import Project
from . import service as refs
from .providers import merge, norm_title, search

MAX_CANDIDATES = 30
QUERY_GAP_S = 4.0
RETRY_GAP_S = 6.0
SCAN_FILE = ("inputs", "scan.json")  # not under references/, whose *.json files are records


def _now() -> str:
    return datetime.now(UTC).isoformat()


def scan_path(root: Path) -> Path:
    return root.joinpath(*SCAN_FILE)


def load_scan(root: Path) -> dict | None:
    p = scan_path(root)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_scan(root: Path, data: dict) -> None:
    storage.write_text(scan_path(root), json.dumps(data, indent=2, ensure_ascii=False))


def exemplar_metas(root: Path) -> list[dict]:
    out = []
    d = root / "exemplars"
    if d.exists():
        for sub in sorted(d.iterdir()):
            meta = ingest_extract.read_meta(sub) if sub.is_dir() else None
            if meta:
                out.append(meta)
    return out


def _identity(d: dict) -> set[str]:
    ids = set()
    if d.get("doi"):
        ids.add("doi:" + str(d["doi"]).lower().strip())
    if d.get("arxiv_id"):
        ids.add("arxiv:" + re.sub(r"v\d+$", "", str(d["arxiv_id"])))
    if d.get("title"):
        ids.add("title:" + norm_title(d["title"]))
    return ids


def _known(root: Path) -> tuple[set[str], set[str]]:
    """Identities already present as references and as exemplars."""
    ref_ids: set[str] = set()
    for r in refs.list_records(root):
        ref_ids |= _identity(r)
    ex_ids: set[str] = set()
    for m in exemplar_metas(root):
        ex_ids |= _identity(m)
    return ref_ids, ex_ids


async def run_scan(project_id: str, ctx: JobContext) -> dict:
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if not project:
            raise ValueError("Project not found")
        db.expunge(project)
    root = storage.project_dir(project.slug)
    kname = kind_name(project.kind) if kind_exists(project.kind) else project.kind
    idea = storage.read_text(root / "inputs" / "idea.md")
    plan = storage.read_text(root / "inputs" / "research-plan.md")
    spec = storage.read_text(root / "inputs" / "system-spec.md")
    if not (idea.strip() or plan.strip() or spec.strip()):
        raise ValueError("Write the idea, a research plan or the specification first. The scan reads those.")
    metas = exemplar_metas(root)
    known_titles = "\n".join(f"- {m.get('title', '')}" for m in metas if m.get("title"))

    ctx.progress(5, "Choosing search queries")
    q_prompt = render(
        "scan_queries.j2",
        kind_name=kname,
        idea=budget_markdown(idea, 3000),
        plan=budget_markdown(plan, 3000),
        spec=budget_markdown(spec, 6000),
        known=known_titles,
    )
    with SessionLocal() as db:
        p = db.get(Project, project_id)
        q_res = await complete(
            db,
            "utility",
            [Message("user", q_prompt)],
            project=p,
            user_id=ctx.user_id,
            max_tokens=400,
            temperature=0.3,
            json_mode=True,
        )
    q_data = extract_json(q_res.text)
    queries = [str(q).strip() for q in (q_data.get("queries") or []) if str(q).strip()][:6]
    themes = [str(t) for t in (q_data.get("themes") or [])][: len(queries)]
    if not queries:
        raise ValueError("The model returned no search queries. Try again or add more to the specification.")

    lists, errors, hits = [], [], {}
    retry = True  # switched off once an index keeps throttling, so a blocked IP does not double the run time
    for i, q in enumerate(queries):
        ctx.progress(10 + int(50 * i / len(queries)), f"Searching: {q}")
        if i:
            await asyncio.sleep(QUERY_GAP_S)  # Semantic Scholar and arXiv throttle bursts
        cands, errs = await search(q, limit=10)
        if errs and retry:
            await asyncio.sleep(RETRY_GAP_S)
            more, errs2 = await search(q, limit=10)
            cands = merge([cands, more])
            if {e.split(":")[0] for e in errs2} >= {e.split(":")[0] for e in errs}:
                retry = False  # same indexes failed again: systematic, stop paying for retries
            errs = errs2
        errors.extend(errs)
        lists.append(cands)
        for c in cands:
            hits.setdefault(norm_title(c.title), set()).add(i)
    merged = merge(lists)

    ref_ids, ex_ids = _known(root)
    candidates: list[dict] = []
    for c in merged:
        d = c.to_dict()
        ids = _identity(d)
        d["already_reference"] = bool(ids & ref_ids)
        d["already_exemplar"] = bool(ids & ex_ids)
        d["queries"] = sorted(hits.get(norm_title(c.title), set()))
        candidates.append(d)
    fresh = [c for c in candidates if not (c["already_reference"] or c["already_exemplar"])][:MAX_CANDIDATES]
    if not fresh:
        raise ValueError("Every paper found is already in the project. Refine the specification and scan again.")

    ctx.progress(65, f"Ranking {len(fresh)} candidates")
    work = "\n\n".join(
        s for s in (budget_markdown(idea, 1500), budget_markdown(plan, 1500), budget_markdown(spec, 3000)) if s.strip()
    )
    r_prompt = render("scan_rank.j2", kind_name=kname, work=work, candidates=fresh)
    with SessionLocal() as db:
        p = db.get(Project, project_id)
        r_res = await complete(
            db,
            "utility",
            [Message("user", r_prompt)],
            project=p,
            user_id=ctx.user_id,
            max_tokens=2500,
            temperature=0.1,
            json_mode=True,
        )
    ranked = {}
    for item in extract_json(r_res.text).get("ranked") or []:
        try:
            ranked[int(item["idx"])] = (max(0, min(3, int(item.get("relevance", 1)))), str(item.get("why", ""))[:240])
        except (KeyError, TypeError, ValueError):
            continue
    for i, c in enumerate(fresh):
        rel, why = ranked.get(i, (1, ""))
        c["relevance"] = rel
        c["why"] = why
        c["adopted_reference"] = None
        c["adopted_exemplar"] = False
    fresh.sort(key=lambda c: (-c["relevance"], -(c.get("citation_count") or 0), -(c.get("year") or 0)))
    fresh = [c for c in fresh if c["relevance"] > 0]

    data = {
        "queries": queries,
        "themes": themes,
        "candidates": fresh,
        "skipped_known": len(candidates)
        - len([c for c in candidates if not (c["already_reference"] or c["already_exemplar"])]),
        "errors": errors,
        "created_at": _now(),
        "tokens_in": q_res.usage.input_tokens + r_res.usage.input_tokens,
        "tokens_out": q_res.usage.output_tokens + r_res.usage.output_tokens,
    }
    save_scan(root, data)
    storage.git_commit(root, f"Literature scan: {len(fresh)} candidates")
    ctx.progress(100, f"{len(fresh)} papers found, {sum(1 for c in fresh if c['relevance'] == 3)} strong matches")
    return {
        "candidates": len(fresh),
        "strong": sum(1 for c in fresh if c["relevance"] == 3),
        "queries": len(queries),
        "tokens_in": data["tokens_in"],
        "tokens_out": data["tokens_out"],
    }


def adopt_references(root: Path, idx: list[int]) -> list[str]:
    """Turn chosen candidates into verified reference records. Returns the keys."""
    data = load_scan(root)
    if not data:
        raise ValueError("No scan to adopt from")
    added = []
    for i in idx:
        if not 0 <= i < len(data["candidates"]):
            continue
        c = data["candidates"][i]
        if c.get("adopted_reference"):
            added.append(c["adopted_reference"])
            continue
        rec = refs.accept(root, c)
        c["adopted_reference"] = rec["key"]
        added.append(rec["key"])
    save_scan(root, data)
    return added


def mark_exemplar(root: Path, idx: int) -> None:
    mark_adopted(root, idx, "adopted_exemplar")


def mark_adopted(root: Path, idx: int, field: str) -> None:
    data = load_scan(root)
    if data and 0 <= idx < len(data["candidates"]):
        data["candidates"][idx][field] = True
        save_scan(root, data)


def candidate_from_meta(meta: dict) -> dict:
    """An exemplar's metadata in the shape `refs.accept` expects."""
    return {
        "title": meta.get("title") or "",
        "authors": meta.get("authors") or [],
        "year": meta.get("year"),
        "venue": meta.get("journal_ref") or None,
        "doi": meta.get("doi") or None,
        "url": meta.get("url") or (f"https://arxiv.org/abs/{meta['arxiv_id']}" if meta.get("arxiv_id") else None),
        "arxiv_id": meta.get("arxiv_id"),
        "abstract": meta.get("abstract"),
        "bibtype": "article" if meta.get("journal_ref") else "misc",
        "source": "exemplar",
        "sources": ["arxiv"] if meta.get("arxiv_id") else ["pdf"],
    }


def existing_key_for(root: Path, cand: dict) -> str | None:
    ids = _identity(cand)
    for r in refs.list_records(root):
        if ids & _identity(r):
            return r["key"]
    return None
