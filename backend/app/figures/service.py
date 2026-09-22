"""Figures (SPEC 4.8): Mermaid diagrams rendered in the browser, uploaded images for results.

figures/index.json          [{name, kind, caption, file, source_file, png_file, created_at}]
figures/<name>.mmd          Mermaid source (kind = mermaid)
figures/<name>.svg          rendered by the browser
figures/<name>.png          rasterised by the browser, used in LaTeX and DOCX
figures/<name>.<ext>        uploaded image (kind = image)
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from .. import storage
from ..db import SessionLocal
from ..learn.context import budget_markdown, render
from ..llm.base import Message
from ..llm.registry import complete
from ..models import Project

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,40}$")
IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/svg+xml": ".svg",
    "application/pdf": ".pdf",
    "image/webp": ".webp",
}


def _dir(root: Path) -> Path:
    d = root / "figures"
    d.mkdir(exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(UTC).isoformat()


def load(root: Path) -> list[dict]:
    p = _dir(root) / "index.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []


def save(root: Path, items: list[dict]) -> None:
    storage.write_text(_dir(root) / "index.json", json.dumps(items, indent=2, ensure_ascii=False))


def get(root: Path, name: str) -> dict | None:
    return next((f for f in load(root) if f["name"] == name), None)


def slug_name(name: str, taken: set[str]) -> str:
    base = storage.slugify(name, max_length=40) or "figure"
    n, cand = 2, base
    while cand in taken:
        cand = f"{base}-{n}"
        n += 1
    return cand


def create_mermaid(root: Path, name: str, caption: str, source: str) -> dict:
    items = load(root)
    n = slug_name(name, {f["name"] for f in items})
    storage.write_text(_dir(root) / f"{n}.mmd", source.strip() + "\n")
    item = {
        "name": n,
        "kind": "mermaid",
        "caption": caption.strip(),
        "file": None,
        "source_file": f"{n}.mmd",
        "png_file": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    items.append(item)
    save(root, items)
    storage.git_commit(root, f"Figure: add {n}")
    return item


def update(root: Path, name: str, *, caption: str | None = None, source: str | None = None) -> dict:
    items = load(root)
    item = next((f for f in items if f["name"] == name), None)
    if not item:
        raise ValueError("Figure not found")
    if caption is not None:
        item["caption"] = caption.strip()
    if source is not None and item["kind"] == "mermaid":
        storage.write_text(_dir(root) / item["source_file"], source.strip() + "\n")
        # rendered outputs are stale until the browser re-renders
        for key in ("file", "png_file"):
            if item.get(key):
                (_dir(root) / item[key]).unlink(missing_ok=True)
                item[key] = None
    item["updated_at"] = _now()
    save(root, items)
    storage.git_commit(root, f"Figure: update {name}")
    return item


def store_render(root: Path, name: str, svg: bytes | None, png: bytes | None) -> dict:
    items = load(root)
    item = next((f for f in items if f["name"] == name), None)
    if not item:
        raise ValueError("Figure not found")
    if svg:
        (_dir(root) / f"{name}.svg").write_bytes(svg)
        item["file"] = f"{name}.svg"
    if png:
        (_dir(root) / f"{name}.png").write_bytes(png)
        item["png_file"] = f"{name}.png"
    item["updated_at"] = _now()
    save(root, items)
    storage.git_commit(root, f"Figure: render {name}")
    return item


def create_image(root: Path, name: str, caption: str, data: bytes, content_type: str) -> dict:
    ext = IMAGE_TYPES.get(content_type)
    if not ext:
        raise ValueError("Use PNG, JPEG, SVG, WebP or PDF")
    items = load(root)
    n = slug_name(name, {f["name"] for f in items})
    (_dir(root) / f"{n}{ext}").write_bytes(data)
    item = {
        "name": n,
        "kind": "image",
        "caption": caption.strip(),
        "file": f"{n}{ext}",
        "source_file": None,
        "png_file": f"{n}{ext}" if ext in (".png", ".jpg", ".pdf") else None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    items.append(item)
    save(root, items)
    storage.git_commit(root, f"Figure: upload {n}")
    return item


def delete(root: Path, name: str) -> bool:
    items = load(root)
    item = next((f for f in items if f["name"] == name), None)
    if not item:
        return False
    for key in ("file", "source_file", "png_file"):
        if item.get(key):
            (_dir(root) / item[key]).unlink(missing_ok=True)
    save(root, [f for f in items if f["name"] != name])
    storage.git_commit(root, f"Figure: remove {name}")
    return True


def source(root: Path, item: dict) -> str:
    return storage.read_text(_dir(root) / item["source_file"]) if item.get("source_file") else ""


def file_path(root: Path, name: str, which: str = "file") -> Path | None:
    item = get(root, name)
    if not item or not item.get(which):
        return None
    p = (_dir(root) / item[which]).resolve()
    return p if p.exists() and _dir(root).resolve() in p.parents else None


async def generate_mermaid(project_id: str, user_id: str, prompt: str, diagram: str) -> str:
    """Ask the utility model for a Mermaid diagram of the system, from the spec plus a request."""
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if not project:
            raise ValueError("Project not found")
        root = storage.project_dir(project.slug)
        spec = budget_markdown(storage.read_text(root / "inputs" / "system-spec.md"), 8000)
        facts = storage.read_text(root / "inputs" / "facts.md")[:3000]
        text = render("mermaid.j2", diagram=diagram, request=prompt.strip(), spec=spec, facts=facts)
        result = await complete(
            db, "utility", [Message("user", text)], project=project, user_id=user_id, max_tokens=1200, temperature=0.2
        )
    out = result.text.strip()
    m = re.search(r"```(?:mermaid)?\s*\n(.*?)```", out, re.DOTALL)
    return (m.group(1) if m else out).strip()
