"""Context budgeting (SPEC 3.4).

`budget_markdown` trims a paper to a character budget while keeping every section
represented: each section receives a share proportional to its length, with a floor,
and keeps its opening text. The model sees the whole shape of the paper, not just the
first pages.
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..ingest.extract import sections_of

_PROMPTS = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "prompts")),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
)


def render(name: str, **kwargs) -> str:
    return _PROMPTS.get_template(name).render(**kwargs)


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _cut(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    cut = text[:n]
    # end on a sentence or paragraph boundary when one is near
    for sep in ("\n\n", ". ", "\n"):
        i = cut.rfind(sep)
        if i > n * 0.6:
            return cut[: i + len(sep)].rstrip() + "\n\n[...]\n"
    return cut.rstrip() + " [...]\n"


def budget_markdown(md: str, max_chars: int, *, min_per_section: int = 400) -> str:
    if len(md) <= max_chars:
        return md
    secs = sections_of(md)
    if not secs:
        return _cut(md, max_chars)

    preamble = md[: secs[0]["start"]]
    parts: list[tuple[str, str]] = []  # (heading line, body)
    for i, s in enumerate(secs):
        end = secs[i + 1]["start"] if i + 1 < len(secs) else len(md)
        chunk = md[s["start"] : end]
        nl = chunk.find("\n")
        heading, body = (chunk, "") if nl == -1 else (chunk[:nl], chunk[nl + 1 :])
        parts.append((heading, body))

    # Drop references / bibliography bodies entirely; they are noise for learning.
    def is_refs(h: str) -> bool:
        return bool(re.search(r"\b(references|bibliography)\b", h, re.I))

    total_body = sum(len(b) for h, b in parts if not is_refs(h)) or 1
    overhead = len(preamble) + sum(len(h) + 2 for h, _ in parts)
    available = max(max_chars - overhead, min_per_section * len(parts))

    out = [_cut(preamble, min(len(preamble), max_chars // 8))]
    for heading, body in parts:
        if is_refs(heading):
            out.append(heading + "\n\n[references omitted]\n\n")
            continue
        share = int(available * (len(body) / total_body))
        share = max(min(share, len(body)), min(min_per_section, len(body)))
        out.append(heading + "\n" + _cut(body, share) + "\n")
    result = "".join(out)
    return result if len(result) <= max_chars * 1.15 else _cut(result, max_chars)


def sample_for_style(md: str, max_chars: int) -> str:
    """For voice learning: intro, one middle body section and the conclusion, plus a slice of the rest."""
    secs = sections_of(md)
    if not secs or len(md) <= max_chars:
        return budget_markdown(md, max_chars)
    chosen = []
    for s in secs:
        t = s["title"].lower()
        if any(k in t for k in ("introduction", "conclusion", "discussion")):
            chosen.append(s)
    body_secs = [
        s for s in secs if s not in chosen and not re.search(r"references|bibliography|abstract", s["title"], re.I)
    ]
    if body_secs:
        chosen.append(body_secs[len(body_secs) // 2])
    if not chosen:
        return budget_markdown(md, max_chars)
    per = max_chars // len(chosen)
    out = []
    for s in sorted(chosen, key=lambda x: x["start"]):
        end = md.find("\n#", s["start"] + 1)
        end = len(md) if end == -1 else end
        out.append(_cut(md[s["start"] : end], per))
    return "\n\n".join(out)
