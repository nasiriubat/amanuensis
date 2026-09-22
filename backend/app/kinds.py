"""Paper kinds: Markdown folders under DATA_DIR/kinds.

Each kind has kind.md, sections.md, interview.md and checklist.md. The first line of
kind.md is the display name as an H1; the first paragraph after it is the summary.
"""

from __future__ import annotations

import re
import shutil

from . import storage
from .config import get_settings


def _parse_kind_md(text: str) -> tuple[str, str]:
    name = None
    summary = ""
    lines = text.splitlines()
    i = 0
    for i, line in enumerate(lines):  # noqa: B007
        if line.startswith("# "):
            name = line[2:].strip()
            break
    para: list[str] = []
    for line in lines[i + 1 :]:
        if not line.strip():
            if para:
                break
            continue
        if line.startswith("#"):
            break
        para.append(line.strip())
    summary = " ".join(para)
    return name or "Untitled kind", summary


def list_kinds() -> list[dict]:
    root = storage.kinds_dir()
    builtin_names = {d.name for d in (get_settings().seed_dir / "kinds").iterdir() if d.is_dir()}
    out = []
    if not root.exists():
        return out
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        name, summary = _parse_kind_md(storage.read_text(d / "kind.md"))
        out.append({"slug": d.name, "name": name, "summary": summary, "builtin": d.name in builtin_names})
    # "other" last, the rest alphabetical by name
    out.sort(key=lambda k: (k["slug"] == "other", k["name"].lower()))
    return out


def kind_exists(slug: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9-]{1,64}", slug)) and (storage.kind_dir(slug) / "kind.md").exists()


def kind_name(slug: str) -> str:
    if not kind_exists(slug):
        return slug
    name, _ = _parse_kind_md(storage.read_text(storage.kind_dir(slug) / "kind.md"))
    return name


def read_kind(slug: str) -> dict:
    d = storage.kind_dir(slug)
    name, summary = _parse_kind_md(storage.read_text(d / "kind.md"))
    builtin = (get_settings().seed_dir / "kinds" / slug).is_dir()
    files = {f: storage.read_text(d / f) for f in storage.KIND_FILES}
    return {"slug": slug, "name": name, "summary": summary, "builtin": builtin, "files": files}


def create_kind(name: str, summary: str) -> dict:
    base = storage.slugify(name, max_length=40)
    slug = storage.unique_slug(base, kind_exists)
    d = storage.kind_dir(slug)
    d.mkdir(parents=True)
    (d / "kind.md").write_text(
        f"# {name}\n\n{summary}\n\n## What reviewers expect\n\n## Common reasons for rejection\n", encoding="utf-8"
    )
    (d / "sections.md").write_text("# Default sections\n\n1. **Introduction** — \n", encoding="utf-8")
    (d / "interview.md").write_text("# Interview rounds\n\n## Round 1: \n\n- \n", encoding="utf-8")
    (d / "checklist.md").write_text("# Required evidence\n\n- \n", encoding="utf-8")
    return read_kind(slug)


def write_kind_file(slug: str, filename: str, content: str) -> None:
    if filename not in storage.KIND_FILES:
        raise ValueError("Unknown kind file")
    storage.write_text(storage.kind_dir(slug) / filename, content)


def delete_kind(slug: str) -> None:
    if slug == "other":
        raise ValueError("The 'other' kind cannot be deleted")
    shutil.rmtree(storage.kind_dir(slug))


def reset_kind(slug: str) -> None:
    """Restore a built-in kind to the shipped version."""
    src = get_settings().seed_dir / "kinds" / slug
    if not src.is_dir():
        raise ValueError("Not a built-in kind")
    dst = storage.kind_dir(slug)
    for f in src.iterdir():
        shutil.copy2(f, dst / f.name)
