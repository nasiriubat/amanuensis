"""PDF to Markdown.

Docling when installed (the Docker image ships it): layout-aware, tables, figures with
captions. Otherwise pypdfium2 text with heading heuristics, which is good enough for
the model to read but keeps no tables or figures.
"""

from __future__ import annotations

import re
from pathlib import Path


def docling_available() -> bool:
    try:
        import docling  # noqa: F401

        return True
    except Exception:
        return False


def pdf_to_markdown_docling(pdf: Path, out_dir: Path) -> tuple[str, list[dict]]:
    from docling.document_converter import DocumentConverter

    conv = DocumentConverter()
    result = conv.convert(str(pdf))
    doc = result.document
    md = doc.export_to_markdown()
    figures: list[dict] = []
    fig_dir = out_dir / "figures"
    for i, pic in enumerate(getattr(doc, "pictures", []) or []):
        try:
            img = pic.get_image(doc)
        except Exception:
            img = None
        caption = ""
        try:
            caption = pic.caption_text(doc) or ""
        except Exception:
            pass
        entry = {"index": i + 1, "caption": caption, "file": None}
        if img is not None:
            fig_dir.mkdir(parents=True, exist_ok=True)
            path = fig_dir / f"figure-{i + 1}.png"
            img.save(path)
            entry["file"] = str(path.relative_to(out_dir))
        figures.append(entry)
    return md, figures


_HEADING = re.compile(r"^\s*(\d+(?:\.\d+){0,2})\.?\s+([A-Z][^\n]{2,80})$")
_KNOWN = {
    "abstract",
    "introduction",
    "background",
    "related work",
    "method",
    "methods",
    "methodology",
    "approach",
    "design",
    "implementation",
    "evaluation",
    "results",
    "discussion",
    "threats to validity",
    "limitations",
    "conclusion",
    "conclusions",
    "conclusion and future work",
    "future work",
    "acknowledgments",
    "acknowledgements",
    "references",
}


def pdf_to_markdown_pdfium(pdf: Path) -> str:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf))
    pages = []
    for page in doc:
        text = page.get_textpage().get_text_bounded()
        pages.append(text)
    raw = "\n".join(pages)

    # de-hyphenate line breaks, join wrapped lines inside paragraphs
    raw = re.sub(r"-\n(?=[a-z])", "", raw)
    lines = [ln.rstrip() for ln in raw.split("\n")]
    out: list[str] = []
    para: list[str] = []

    def flush():
        if para:
            out.append(" ".join(para))
            para.clear()

    for ln in lines:
        s = ln.strip()
        if not s:
            flush()
            continue
        m = _HEADING.match(s)
        if m and len(s) < 90:
            flush()
            level = m.group(1).count(".") + 2
            out.append("\n" + "#" * min(level, 4) + " " + m.group(2).strip() + "\n")
            continue
        if s.lower() in _KNOWN and len(s) < 40:
            flush()
            out.append("\n## " + s.title() + "\n")
            continue
        para.append(s)
    flush()
    md = "\n\n".join(x for x in out if x.strip())
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md


def pdf_to_markdown(pdf: Path, out_dir: Path) -> tuple[str, list[dict], str]:
    """Returns (markdown, figures, method)."""
    if docling_available():
        try:
            md, figs = pdf_to_markdown_docling(pdf, out_dir)
            return md, figs, "docling"
        except Exception:
            pass
    return pdf_to_markdown_pdfium(pdf), [], "pdfium"
