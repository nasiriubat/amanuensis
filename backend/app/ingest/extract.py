"""Turn a downloaded source (LaTeX tree or PDF) into extracted.md + meta.json.

Layout of one exemplar folder:
    <id>/
      meta.json        title, authors, year, source, sections, figures, word_count
      extracted.md     the paper as Markdown
      src/             LaTeX tree (arXiv source) or empty
      source.pdf       when a PDF was used
      refs.bib         concatenated .bib files when present
      figures/         extracted images (PDF via Docling) or copies from the LaTeX tree
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from . import latex as latex_mod
from . import pdf as pdf_mod

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$", re.MULTILINE)


def sections_of(md: str) -> list[dict]:
    """[{level, title, start, chars, words}] for each heading in the Markdown."""
    heads = list(_HEADING_RE.finditer(md))
    out = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(md)
        body = md[h.end() : end]
        out.append(
            {
                "level": len(h.group(1)),
                "title": h.group(2).strip(),
                "start": h.start(),
                "chars": len(body),
                "words": len(body.split()),
            }
        )
    return out


def _figures_from_markdown(md: str) -> list[dict]:
    figs = []
    for m in re.finditer(r"^> \*\*(Figure|Table|Algorithm) (\d+)\.\*\* (.*)$", md, re.MULTILINE):
        figs.append({"kind": m.group(1).lower(), "index": int(m.group(2)), "caption": m.group(3).strip()})
    return figs


def _copy_latex_figures(src_dir: Path, out_dir: Path) -> list[str]:
    fig_dir = out_dir / "figures"
    copied = []
    for p in src_dir.rglob("*"):
        if (
            p.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".svg", ".eps"}
            and p.is_file()
            and p.name != "source.pdf"
        ):
            if p.suffix.lower() == ".pdf" and p.stat().st_size > 5 * 1024 * 1024:
                continue
            fig_dir.mkdir(parents=True, exist_ok=True)
            target = fig_dir / p.name
            if not target.exists():
                shutil.copy2(p, target)
                copied.append(target.name)
        if len(copied) >= 40:
            break
    return copied


def extract_latex_tree(out_dir: Path, meta: dict) -> dict:
    src_dir = out_dir / "src"
    main = latex_mod.find_main_tex(src_dir)
    if main is None:
        raise ValueError("No .tex file with \\documentclass found in the arXiv source")
    tex = latex_mod.flatten(main)
    md, method = latex_mod.latex_to_markdown(tex)
    if not meta.get("title"):
        m = re.search(r"^# (.+)$", md, re.MULTILINE)
        meta["title"] = m.group(1).strip() if m else main.stem
    bibs = latex_mod.find_bib_files(src_dir)
    if bibs:
        (out_dir / "refs.bib").write_text(
            "\n\n".join(b.read_text(encoding="utf-8", errors="ignore") for b in bibs), encoding="utf-8"
        )
    figures = _figures_from_markdown(md)
    files = _copy_latex_figures(src_dir, out_dir)
    return _finish(out_dir, md, meta, source="arxiv-latex", method=method, figures=figures, figure_files=files)


def extract_pdf(out_dir: Path, pdf: Path, meta: dict) -> dict:
    md, figures, method = pdf_mod.pdf_to_markdown(pdf, out_dir)
    if not meta.get("title"):
        first = next((ln.strip("# ").strip() for ln in md.splitlines() if ln.strip()), None)
        meta["title"] = (first or pdf.stem)[:200]
    return _finish(
        out_dir,
        md,
        meta,
        source=meta.get("source") or "pdf",
        method=method,
        figures=figures,
        figure_files=[f["file"] for f in figures if f.get("file")],
    )


def _finish(
    out_dir: Path, md: str, meta: dict, *, source: str, method: str, figures: list[dict], figure_files: list[str]
) -> dict:
    md = md.strip() + "\n"
    (out_dir / "extracted.md").write_text(md, encoding="utf-8")
    secs = sections_of(md)
    meta.update(
        {
            "source": source,
            "extraction": method,
            "sections": secs,
            "figures": figures,
            "figure_files": figure_files,
            "word_count": len(md.split()),
            "char_count": len(md),
            "extracted_at": datetime.now(UTC).isoformat(),
            "status": "ready",
        }
    )
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def read_meta(folder: Path) -> dict | None:
    p = folder / "meta.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
