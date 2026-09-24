"""Fix issues (ROADMAP item 1): propose a cleaned section; the author accepts or discards.

Two stages. The mechanical pass in `hygiene.py` handles dashes, semicolons, exclamation marks
and spacing for free. What the lint still flags goes to the utility model with the findings
and the hygiene rules. Nothing is saved here; the router returns the proposal and the
Studio shows a diff.
"""

from __future__ import annotations

import re

from .. import storage
from ..learn.context import render
from ..llm.base import Message
from ..llm.registry import complete
from ..models import Project
from . import hygiene
from . import lint as lint_mod

# Findings the model may act on. Citation keys and [NEEDS] items are the author's to resolve.
MODEL_FIXABLE = {"banned", "dash", "semicolon", "long", "opener", "exclamation", "question", "overlap"}
MAX_FINDINGS = 40
WORD_TOLERANCE = 0.25

_CITES = re.compile(r"\[@[^\]]*\]")
_PLACEHOLDERS = re.compile(r"\[(?:NEEDS|CITE):[^\]]*\]")
_STRUCTURE = re.compile(r"^(?:#{1,6}\s|!\[|\||```)", re.MULTILINE)


def hygiene_rules(house_style: str) -> str:
    """Punctuation, banned phrases and patterns: the parts a copy editor enforces."""
    keep = ("## Punctuation", "## Banned words and phrases", "## Patterns to avoid", "## Sentences")
    out: list[str] = []
    for m in re.finditer(r"^(## .+?)\n(.*?)(?=^## |\Z)", house_style, re.MULTILINE | re.DOTALL):
        if m.group(1).strip() in keep:
            out.append(m.group(0).strip())
    return "\n\n".join(out) or house_style


def preserved(before: str, after: str) -> str | None:
    """Return a reason when the revision dropped something the author must keep, else None."""
    if sorted(_CITES.findall(before)) != sorted(_CITES.findall(after)):
        return "the citations changed"
    if sorted(_PLACEHOLDERS.findall(before)) != sorted(_PLACEHOLDERS.findall(after)):
        return "a placeholder was dropped or altered"
    if _STRUCTURE.findall(before) != _STRUCTURE.findall(after):
        return "a heading, figure, table or code block changed"
    wb, wa = len(before.split()), len(after.split())
    if wb >= 40 and abs(wa - wb) > wb * WORD_TOLERANCE:
        return f"the length changed too much ({wb} to {wa} words)"
    return None


def _fixable(findings: list[dict]) -> list[dict]:
    return [f for f in findings if f["kind"] in MODEL_FIXABLE][:MAX_FINDINGS]


async def propose(project: Project, text: str, known_keys: set[str], exemplars: dict[str, str], user_id: str) -> dict:
    house = storage.read_text(storage.house_style_path())
    before = lint_mod.lint(text, house, known_keys, exemplars)

    cleaned, changes = hygiene.mechanical_pass(text)
    remaining = lint_mod.lint(cleaned, house, known_keys, exemplars)
    todo = _fixable(remaining)

    note = ""
    tokens_in = tokens_out = 0
    model_used = False
    if todo:
        prompt = render("fix_section.j2", house_style=hygiene_rules(house), findings=todo, text=cleaned)
        from ..db import SessionLocal

        with SessionLocal() as db:
            p = db.get(Project, project.id)
            result = await complete(
                db,
                "utility",
                [Message("user", prompt)],
                project=p,
                user_id=user_id,
                max_tokens=max(1200, int(len(cleaned.split()) * 2.0) + 400),
                temperature=0.2,
            )
        tokens_in, tokens_out = result.usage.input_tokens, result.usage.output_tokens
        candidate = re.sub(r"^```[a-z]*\n|\n```$", "", result.text.strip()).strip()
        reason = preserved(cleaned, candidate)
        if reason:
            note = f"The model's version was set aside because {reason}. Only the mechanical fixes are proposed."
        else:
            cleaned = candidate
            model_used = True
            remaining = lint_mod.lint(cleaned, house, known_keys, exemplars)
    if cleaned.strip() == text.strip() and not note:
        note = "Nothing here can be fixed automatically. The remaining findings need your judgement."

    return {
        "text": cleaned,
        "changed": cleaned.strip() != text.strip(),
        "mechanical": hygiene.describe(changes),
        "model_used": model_used,
        "before": lint_mod.summarize(before),
        "before_count": len(before),
        "after": remaining,
        "note": note,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
