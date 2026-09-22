"""Reference records (SPEC 4.4): one JSON per key, refs.bib regenerated from them."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from .. import storage
from . import bib as bib_mod
from .providers import Candidate, search

_KEY_RE = re.compile(r"^[A-Za-z0-9_:\-]{1,80}$")
_CITE = re.compile(r"\[CITE:\s*([^\]]+)\]")


def _dir(root: Path) -> Path:
    d = root / "references"
    d.mkdir(exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(UTC).isoformat()


def list_records(root: Path) -> list[dict]:
    out = []
    for p in sorted(_dir(root).glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    out.sort(key=lambda r: r.get("added_at") or "", reverse=True)
    return out


def get_record(root: Path, key: str) -> dict | None:
    if not _KEY_RE.match(key):
        return None
    p = _dir(root) / f"{key}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def keys(root: Path) -> set[str]:
    return {p.stem for p in _dir(root).glob("*.json")}


def rewrite_bib(root: Path) -> None:
    records = sorted(list_records(root), key=lambda r: r["key"])
    text = "\n\n".join(bib_mod.record_to_bibtex(r) for r in records) + ("\n" if records else "")
    storage.write_text(_dir(root) / "refs.bib", text)


def _save(root: Path, record: dict) -> dict:
    storage.write_text(_dir(root) / f"{record['key']}.json", json.dumps(record, indent=2, ensure_ascii=False))
    rewrite_bib(root)
    return record


def accept(root: Path, cand: dict, *, key: str | None = None) -> dict:
    """Turn a search candidate into a verified record."""
    taken = keys(root)
    k = (
        key
        if key and _KEY_RE.match(key) and key not in taken
        else bib_mod.make_key(cand.get("authors") or [], cand.get("year"), cand.get("title") or "", taken)
    )
    record = {
        "key": k,
        "title": (cand.get("title") or "").strip(),
        "authors": [a for a in (cand.get("authors") or []) if a],
        "year": cand.get("year"),
        "venue": cand.get("venue"),
        "doi": cand.get("doi"),
        "url": cand.get("url"),
        "arxiv_id": cand.get("arxiv_id"),
        "abstract": cand.get("abstract"),
        "citation_count": cand.get("citation_count"),
        "bibtype": cand.get("bibtype") or "misc",
        "source": cand.get("source") or (cand.get("sources") or ["manual"])[0],
        "sources": cand.get("sources") or ([cand["source"]] if cand.get("source") else []),
        "verified_at": _now(),
        "added_at": _now(),
        "snippet": cand.get("snippet"),
    }
    if not record["title"]:
        raise ValueError("A reference needs a title")
    _save(root, record)
    storage.git_commit(root, f"Reference: add {k}")
    return record


def add_manual(root: Path, data: dict) -> dict:
    data = dict(data)
    data["source"] = "manual"
    return accept(root, data, key=data.get("key"))


def delete(root: Path, key: str) -> bool:
    if not _KEY_RE.match(key):
        return False
    p = _dir(root) / f"{key}.json"
    if not p.exists():
        return False
    p.unlink()
    rewrite_bib(root)
    storage.git_commit(root, f"Reference: remove {key}")
    return True


def import_bib(root: Path, text: str) -> dict:
    entries = bib_mod.parse_bib(text)
    taken = keys(root)
    added, skipped = [], []
    for e in entries:
        rec = bib_mod.entry_to_record(e)
        if not rec["title"]:
            skipped.append(e["key"])
            continue
        k = (
            rec["key"]
            if _KEY_RE.match(rec["key"]) and rec["key"] not in taken
            else bib_mod.make_key(rec["authors"], rec["year"], rec["title"], taken)
        )
        taken.add(k)
        rec.update(
            {
                "key": k,
                "source": "bib",
                "sources": ["bib"],
                "verified_at": _now(),
                "added_at": _now(),
                "citation_count": None,
                "snippet": None,
            }
        )
        storage.write_text(_dir(root) / f"{k}.json", json.dumps(rec, indent=2, ensure_ascii=False))
        added.append(k)
    rewrite_bib(root)
    if added:
        storage.git_commit(root, f"Reference: import {len(added)} from .bib")
    return {"added": added, "skipped": skipped}


def requests(root: Path) -> list[dict]:
    """[CITE: ...] placeholders across sections, with a search query each."""
    out = []
    index_p = root / "sections" / "index.json"
    sections = []
    if index_p.exists():
        try:
            sections = json.loads(index_p.read_text(encoding="utf-8")).get("sections", [])
        except json.JSONDecodeError:
            sections = []
    seen = set()
    for s in sections:
        text = storage.read_text(root / "sections" / s["file"])
        for m in _CITE.finditer(text):
            t = m.group(1).strip()
            if (s["title"], t.lower()) in seen:
                continue
            seen.add((s["title"], t.lower()))
            query = re.sub(
                r"^(a |the |evidence (that|for) |source (for|that) |citation (for|that) )", "", t, flags=re.I
            )
            out.append({"section": s["title"], "section_id": s["id"], "text": t, "query": query[:200]})
    return out


def usage(root: Path) -> dict[str, int]:
    """How many times each key is cited across sections."""
    counts: dict[str, int] = {}
    index_p = root / "sections" / "index.json"
    if not index_p.exists():
        return counts
    try:
        sections = json.loads(index_p.read_text(encoding="utf-8")).get("sections", [])
    except json.JSONDecodeError:
        return counts
    for s in sections:
        text = storage.read_text(root / "sections" / s["file"])
        for m in re.finditer(r"\[(@[^\]]+)\]", text):
            for k in re.findall(r"@([^\]\s;]+)", m.group(1)):
                counts[k] = counts.get(k, 0) + 1
    return counts


async def run_search(q: str, limit: int = 12) -> dict:
    cands, errors = await search(q, limit)
    return {"results": [c.to_dict() for c in cands], "errors": errors}


def candidate_from_dict(d: dict) -> Candidate:
    return Candidate(**{k: v for k, v in d.items() if k in Candidate.__dataclass_fields__})
