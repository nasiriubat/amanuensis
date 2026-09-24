"""Studio: sections derived from the approved outline, drafting, checklist, versions (SPEC 4.6, 4.7).

Files:
    sections/index.json         ordered section metadata
    sections/NN-<slug>.md       one file per section, git-versioned
    checklist.json              open items per section
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

from .. import storage
from ..db import SessionLocal
from ..ingest import extract as ingest_extract
from ..jobs import JobContext
from ..kinds import kind_exists, kind_name, read_kind
from ..learn.context import budget_markdown, render
from ..llm.base import Message
from ..llm.registry import complete
from ..models import AuthorProfile, Project
from . import lint as lint_mod

_HEAD = re.compile(r"^##\s+(?:(\d+)\.\s*)?(.+?)\s*(?:\(≈?\s*(\d[\d,]*)\s*words?\))?\s*$")
_NEEDS = re.compile(r"\[(NEEDS|CITE):\s*([^\]]+)\]")

SECTION_HINTS: dict[str, tuple[str, ...]] = {
    "abstract": ("abstract",),
    "introduction": ("introduction", "intro"),
    "background": ("background", "motivation", "preliminaries"),
    "related": ("related work", "related", "prior work", "state of the art"),
    "design": (
        "design",
        "approach",
        "architecture",
        "overview",
        "method",
        "system",
        "tool",
        "workflow",
        "implementation",
    ),
    "evaluation": ("evaluation", "results", "experiment", "case study", "demonstration", "validation"),
    "discussion": ("discussion", "limitations", "threats"),
    "conclusion": ("conclusion", "future work", "summary"),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _slug(title: str) -> str:
    return storage.slugify(title, max_length=40)


def _bucket(title: str) -> str | None:
    t = title.lower()
    for bucket, words in SECTION_HINTS.items():
        if any(w in t for w in words):
            return bucket
    return None


# ------------------------------------------------------------------ outline parsing


def parse_outline(md: str) -> list[dict]:
    sections: list[dict] = []
    current: dict | None = None
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            if re.match(r"^##\s+open items", line, re.I):
                current = None
                continue
            m = _HEAD.match(line)
            title = (m.group(2) if m else line[3:]).strip()
            words = int(m.group(3).replace(",", "")) if m and m.group(3) else 0
            current = {"title": title, "target_words": words, "lines": []}
            sections.append(current)
        elif current is not None and re.match(r"^\s*[-*]\s+", line):
            current["lines"].append(re.sub(r"^\s*[-*]\s+", "", line).strip())
    return sections


# ------------------------------------------------------------------ index


def _index_path(root: Path) -> Path:
    return root / "sections" / "index.json"


def load_index(root: Path) -> dict:
    p = _index_path(root)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"sections": [], "initialized_at": None}


def save_index(root: Path, index: dict) -> None:
    storage.write_text(_index_path(root), json.dumps(index, indent=2, ensure_ascii=False))


def section_path(root: Path, sec: dict) -> Path:
    return root / "sections" / sec["file"]


def read_section(root: Path, sec: dict) -> str:
    return storage.read_text(section_path(root, sec))


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", re.sub(r"\[(NEEDS|CITE):[^\]]*\]", "", text)))


def exemplar_texts(root: Path) -> dict[str, str]:
    """Title to extracted text for every ready exemplar; used by the overlap lint."""
    out: dict[str, str] = {}
    d = root / "exemplars"
    if not d.exists():
        return out
    for sub in sorted(d.iterdir()):
        md = sub / "extracted.md"
        if sub.is_dir() and md.exists():
            meta = ingest_extract.read_meta(sub) or {}
            out[meta.get("title") or sub.name] = md.read_text(encoding="utf-8", errors="ignore")
    return out


def section_view(
    root: Path, sec: dict, house_style: str, known_keys: set[str], exemplars: dict[str, str] | None = None
) -> dict:
    text = read_section(root, sec)
    findings = lint_mod.lint(text, house_style, known_keys, exemplars) if text.strip() else []
    return {
        **sec,
        "words": _word_count(text),
        "open_items": len(_NEEDS.findall(text)),
        "lint": lint_mod.summarize(findings),
    }


def init_sections(root: Path) -> dict:
    """Create section files from the outline. Idempotent: existing sections keep their text and status."""
    outline = storage.read_text(root / "outline.md")
    parsed = parse_outline(outline)
    if not parsed:
        raise ValueError("The outline has no '## Section' headings to draft from")
    index = load_index(root)
    existing = {s["slug"]: s for s in index["sections"]}
    new_sections = []
    for i, ps in enumerate(parsed, start=1):
        slug = _slug(ps["title"])
        base = slug
        n = 2
        while slug in {s["slug"] for s in new_sections}:
            slug = f"{base}-{n}"
            n += 1
        old = existing.get(slug)
        sec = old or {
            "id": secrets.token_hex(4),
            "slug": slug,
            "file": f"{i:02d}-{slug}.md",
            "status": "empty",  # empty | drafted | edited | mine
            "created_at": _now(),
        }
        sec.update({"order": i, "title": ps["title"], "target_words": ps["target_words"], "lines": ps["lines"]})
        if old and old["file"] != f"{i:02d}-{slug}.md":
            src = root / "sections" / old["file"]
            dst = root / "sections" / f"{i:02d}-{slug}.md"
            if src.exists() and not dst.exists():
                src.rename(dst)
            sec["file"] = dst.name
        path = section_path(root, sec)
        if not path.exists():
            storage.write_text(path, "")
        new_sections.append(sec)
    index["sections"] = new_sections
    index["initialized_at"] = index.get("initialized_at") or _now()
    save_index(root, index)
    seed_checklist(root, parsed)
    storage.git_commit(root, f"Studio: {len(new_sections)} sections from outline")
    return index


def import_draft(root: Path, markdown: str, title: str) -> dict:
    """Turn an author's existing draft into an outline and sections marked as theirs.

    Every `#`/`##` heading becomes a section; its paragraphs' opening sentences become the
    outline lines so the plan reflects what was actually written. Nothing is rewritten.
    """
    text = markdown.replace("\r\n", "\n").strip()
    if not text:
        raise ValueError("Paste the draft first")
    parts: list[tuple[str, str]] = []
    current_title, buf = None, []
    for line in text.split("\n"):
        m = re.match(r"^#{1,3}\s+(.+?)\s*#*\s*$", line)
        if m:
            if current_title is not None or "".join(buf).strip():
                parts.append((current_title or "Introduction", "\n".join(buf).strip()))
            current_title, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    parts.append((current_title or "Draft", "\n".join(buf).strip()))
    parts = [(t, b) for t, b in parts if b or t]
    # a lone leading title line with no body is the paper title, not a section
    if len(parts) > 1 and not parts[0][1].strip():
        parts = parts[1:]
    if not parts:
        raise ValueError("No sections found. Use ## headings or paste at least one paragraph.")

    outline = [f"# Outline: {title}", ""]
    for i, (sec_title, body) in enumerate(parts, start=1):
        words = _word_count(body)
        outline.append(f"## {i}. {sec_title} (≈ {max(words, 50)} words)")
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip() and not p.strip().startswith("![")]
        for para in paras[:8]:
            first = re.split(r"(?<=[.!?])\s+", para, maxsplit=1)[0]
            outline.append(f"- {first[:160]}")
        if not paras:
            outline.append("- [NEEDS: this section has a heading but no text yet]")
        outline.append("")
    outline.append("## Open items")
    outline.append("")
    outline.append("- Imported from the author's draft; review each section against the paper kind's checklist.")
    storage.write_text(root / "outline.md", "\n".join(outline).strip() + "\n")

    index = init_sections(root)
    by_slug = {s["slug"]: s for s in index["sections"]}
    kept = 0
    for sec_title, body in parts:
        sec = by_slug.get(_slug(sec_title))
        if sec and body:
            save_section_text(root, sec, body, by_user=True)
            update_section_meta(root, sec["id"], status="mine")
            kept += 1
    storage.git_commit(root, f"Imported author's draft: {len(parts)} sections")
    return {"sections": len(parts), "with_text": kept, "words": _word_count(text)}


def get_section(root: Path, section_id: str) -> dict:
    for s in load_index(root)["sections"]:
        if s["id"] == section_id:
            return s
    raise ValueError("Section not found")


def update_section_meta(root: Path, section_id: str, **fields) -> dict:
    index = load_index(root)
    for s in index["sections"]:
        if s["id"] == section_id:
            s.update(fields)
            save_index(root, index)
            return s
    raise ValueError("Section not found")


def save_section_text(root: Path, sec: dict, content: str, *, by_user: bool) -> dict:
    storage.write_text(section_path(root, sec), content.rstrip() + "\n" if content.strip() else "")
    status = sec["status"]
    if by_user and status != "mine":
        status = "edited" if content.strip() else "empty"
    elif not by_user:
        status = "drafted" if content.strip() else "empty"
    sec = update_section_meta(root, sec["id"], status=status, updated_at=_now())
    storage.git_commit(root, f"{'Edit' if by_user else 'Draft'} section: {sec['title']}")
    sync_checklist_from_text(root, sec, content)
    return sec


# ------------------------------------------------------------------ checklist


def load_checklist(root: Path) -> list[dict]:
    p = root / "checklist.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []


def save_checklist(root: Path, items: list[dict]) -> None:
    storage.write_text(root / "checklist.json", json.dumps(items, indent=2, ensure_ascii=False))


def seed_checklist(root: Path, parsed: list[dict]) -> None:
    """Outline [NEEDS] lines become items; kind checklist bullets become items per matching section."""
    items = load_checklist(root)
    seen = {(i["section"], i["text"].lower()) for i in items}

    def add(section: str, text: str, source: str):
        key = (section, text.lower())
        if key not in seen:
            items.append(
                {
                    "id": secrets.token_hex(4),
                    "section": section,
                    "text": text,
                    "source": source,
                    "status": "open",
                    "created_at": _now(),
                }
            )
            seen.add(key)

    for ps in parsed:
        for line in ps["lines"]:
            for m in _NEEDS.finditer(line):
                add(ps["title"], m.group(2).strip(), "outline")
    save_checklist(root, items)


def seed_kind_checklist(root: Path, kind: str, parsed: list[dict]) -> None:
    if not kind_exists(kind):
        return
    text = read_kind(kind)["files"].get("checklist.md", "")
    items = load_checklist(root)
    seen = {(i["section"], i["text"].lower()) for i in items}
    titles = [p["title"] for p in parsed]
    current_heading = "Whole paper"
    for raw in text.splitlines():
        if raw.startswith("## "):
            h = raw[3:].strip()
            b = _bucket(h)
            match = next((t for t in titles if _bucket(t) == b), None) if b else None
            current_heading = match or h
        elif re.match(r"^\s*-\s+", raw):
            t = re.sub(r"^\s*-\s+", "", raw).strip()
            key = (current_heading, t.lower())
            if t and key not in seen:
                items.append(
                    {
                        "id": secrets.token_hex(4),
                        "section": current_heading,
                        "text": t,
                        "source": "kind",
                        "status": "open",
                        "created_at": _now(),
                    }
                )
                seen.add(key)
    save_checklist(root, items)


def sync_checklist_from_text(root: Path, sec: dict, content: str) -> None:
    """Placeholders in the draft become open items; items whose placeholder vanished from a 'draft' source close."""
    items = load_checklist(root)
    present = {m.group(2).strip().lower() for m in _NEEDS.finditer(content)}
    seen = {(i["section"], i["text"].lower()) for i in items}
    for m in _NEEDS.finditer(content):
        t = m.group(2).strip()
        key = (sec["title"], t.lower())
        if key not in seen:
            items.append(
                {
                    "id": secrets.token_hex(4),
                    "section": sec["title"],
                    "text": t,
                    "source": "draft" if m.group(1) == "NEEDS" else "citation",
                    "status": "open",
                    "created_at": _now(),
                }
            )
            seen.add(key)
    for it in items:
        if (
            it["section"] == sec["title"]
            and it["source"] in ("draft", "citation")
            and it["status"] == "open"
            and it["text"].lower() not in present
        ):
            it["status"] = "resolved"
            it["resolved_at"] = _now()
    save_checklist(root, items)


def set_checklist_status(root: Path, item_id: str, status: str) -> dict:
    items = load_checklist(root)
    for it in items:
        if it["id"] == item_id:
            it["status"] = status
            it["resolved_at"] = _now() if status != "open" else None
            save_checklist(root, items)
            return it
    raise ValueError("Checklist item not found")


def add_checklist_item(root: Path, section: str, text: str) -> dict:
    items = load_checklist(root)
    it = {
        "id": secrets.token_hex(4),
        "section": section,
        "text": text.strip(),
        "source": "user",
        "status": "open",
        "created_at": _now(),
    }
    items.append(it)
    save_checklist(root, items)
    return it


# ------------------------------------------------------------------ context helpers


def _ref_key_lines(root: Path) -> str:
    from ..refs import service as refs

    lines = []
    for r in sorted(refs.list_records(root), key=lambda x: x["key"]):
        who = (r.get("authors") or ["?"])[0].split(",")[0]
        lines.append(f"[@{r['key']}] {who} {r.get('year') or ''}: {r.get('title', '')[:120]}")
        abstract = re.sub(r"\s+", " ", (r.get("abstract") or "").strip())
        if abstract:
            lines.append(f"    what it says: {abstract[:420]}")
        else:
            lines.append("    what it says: (no abstract on record; cite it only for its title's topic)")
    return "\n".join(lines)


def known_ref_keys(root: Path) -> set[str]:
    bib = storage.read_text(root / "references" / "refs.bib")
    return set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib))


def _exemplar_excerpts(root: Path, title: str, max_chars_each: int = 2500, max_papers: int = 2) -> str:
    bucket = _bucket(title)
    if not bucket:
        return ""
    out = []
    ex_root = root / "exemplars"
    if not ex_root.exists():
        return ""
    for d in sorted(ex_root.iterdir()):
        meta = ingest_extract.read_meta(d) if d.is_dir() else None
        if not meta or meta.get("status") != "ready":
            continue
        md = storage.read_text(d / "extracted.md")
        secs = meta.get("sections", [])
        for i, s in enumerate(secs):
            if s.get("level", 2) <= 2 and _bucket(s["title"]) == bucket:
                end = secs[i + 1]["start"] if i + 1 < len(secs) else len(md)
                body = md[s["start"] : end]
                body = body[:max_chars_each].rstrip() + ("\n[...]" if end - s["start"] > max_chars_each else "")
                out.append(f"--- {meta.get('title', d.name)[:80]} / {s['title']} ---\n{body}")
                break
        if len(out) >= max_papers:
            break
    return "\n\n".join(out)


def _outline_compact(parsed: list[dict]) -> str:
    return "\n".join(
        f"{i}. {p['title']} (~{p['target_words']} words, {len(p['lines'])} paragraphs)" for i, p in enumerate(parsed, 1)
    )


def _others_openings(root: Path, index: dict, current_id: str) -> str:
    parts = []
    for s in index["sections"]:
        if s["id"] == current_id:
            continue
        text = read_section(root, s).strip()
        if text:
            first = text.split("\n\n")[0]
            parts.append(f"[{s['title']}] {first[:400]}")
    return "\n".join(parts)


def _profile_text(project: Project) -> str:
    if not project.profile_id:
        return ""
    with SessionLocal() as db:
        prof = db.get(AuthorProfile, project.profile_id)
        if not prof:
            return ""
        return storage.read_text(storage.profile_dir(prof.slug) / "style.md")


# ------------------------------------------------------------------ drafting


async def draft_section(
    project_id: str,
    section_id: str,
    ctx: JobContext,
    *,
    instructions: str = "",
    force: bool = False,
    ablate: frozenset[str] = frozenset(),
    dry_run: bool = False,
) -> dict:
    """Draft one section.

    `ablate` may contain "playbook" and/or "exemplars" to leave those out of the prompt, and
    `dry_run` returns the text without saving anything. Both exist for the playbook value test
    (SPEC 10) and are never exposed through the API.
    """
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if not project:
            raise ValueError("Project not found")
        db.expunge(project)
    root = storage.project_dir(project.slug)
    index = load_index(root)
    sec = next((s for s in index["sections"] if s["id"] == section_id), None)
    if not sec:
        raise ValueError("Section not found")
    if sec["status"] == "mine" and not force:
        raise ValueError("This section is marked as yours. Unlock it or confirm regeneration.")

    kname = kind_name(project.kind) if kind_exists(project.kind) else project.kind
    inputs = root / "inputs"
    parsed = parse_outline(storage.read_text(root / "outline.md"))
    prev = next((s for s in index["sections"] if s["order"] == sec["order"] - 1), None)
    playbook = "\n\n".join(
        budget_markdown(storage.read_text(root / "playbook" / f), n)
        for f, n in (("argumentation.md", 3500), ("structure.md", 2500), ("evaluation.md", 2500))
    )
    if "playbook" in ablate:
        playbook = ""
    ctx.progress(15, f"Assembling context for “{sec['title']}”")
    system = render(
        "draft_system.j2",
        kind_name=kname,
        profile=budget_markdown(_profile_text(project), 5000),
        house_style=storage.read_text(storage.house_style_path()),
        playbook=playbook,
        facts=storage.read_text(inputs / "facts.md")[:6000],
        ref_keys=_ref_key_lines(root),
    )
    user = render(
        "draft_section.j2",
        title=project.title,
        section=sec,
        total=len(index["sections"]),
        outline_compact=_outline_compact(parsed),
        instructions=instructions.strip()[:4000],
        current=read_section(root, sec) if instructions.strip() else "",
        spec=budget_markdown(storage.read_text(inputs / "system-spec.md"), 12000),
        interview=storage.read_text(inputs / "interview.md")[:12000],
        plan=budget_markdown(storage.read_text(inputs / "research-plan.md"), 3000),
        previous=budget_markdown(read_section(root, prev), 5000) if prev else "",
        others=_others_openings(root, index, sec["id"])[:3000],
        exemplars="" if "exemplars" in ablate else _exemplar_excerpts(root, sec["title"]),
    )
    ctx.progress(35, "Drafting")
    with SessionLocal() as db:
        p = db.get(Project, project_id)
        result = await complete(
            db,
            "draft",
            [Message("system", system), Message("user", user)],
            project=p,
            section=sec["slug"],
            user_id=ctx.user_id,
            max_tokens=max(1200, int(sec["target_words"] * 2.2) + 400),
            temperature=0.5,
        )
    text = result.text.strip()
    text = re.sub(r"^```[a-z]*\n|\n```$", "", text).strip()
    # drop a leading heading if the model added one anyway
    text = re.sub(r"^#{1,3}\s+.*\n+", "", text, count=1) if text.startswith("#") else text
    words = _word_count(text)
    needs = len(_NEEDS.findall(text))
    if dry_run:
        return {
            "section_id": sec["id"],
            "text": text,
            "words": words,
            "open_items": needs,
            "tokens_in": result.usage.input_tokens,
            "tokens_out": result.usage.output_tokens,
            "cached_tokens": result.usage.cached_tokens,
        }
    sec = save_section_text(root, sec, text, by_user=False)
    ctx.progress(100, f"Drafted “{sec['title']}”: {words} words, {needs} open item(s)")
    with SessionLocal() as db:
        p = db.get(Project, project_id)
        if p and p.stage in ("outline", "interview", "playbook", "sources", "setup"):
            p.stage = "drafting"
            db.commit()
    return {
        "section_id": sec["id"],
        "words": words,
        "open_items": needs,
        "tokens_in": result.usage.input_tokens,
        "tokens_out": result.usage.output_tokens,
        "cached_tokens": result.usage.cached_tokens,
    }


# ------------------------------------------------------------------ versions


def history(root: Path, sec: dict, limit: int = 30) -> list[dict]:
    return storage.git_log(root, f"sections/{sec['file']}", limit=limit)


def version_text(root: Path, sec: dict, sha: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{7,40}", sha):
        raise ValueError("Bad version id")
    return storage.git_show(root, sha, f"sections/{sec['file']}")
