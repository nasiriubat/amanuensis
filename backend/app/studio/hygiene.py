"""Deterministic hygiene pass (ROADMAP item 1 and 2). No LLM.

Applies the mechanical parts of the house style to prose lines: dashes used as sentence
punctuation, semicolons joining independent clauses, exclamation marks, stray spaces.
Bracketed spans ([@key], [NEEDS: …], [CITE: …], link text) and non-prose lines (headings,
code, tables, figures) are never touched. Everything else is left to the author or the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .lint import _is_prose_line

_PROTECTED = re.compile(r"\[[^\]]*\]|`[^`]*`|\$[^$]+\$")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


@dataclass
class Change:
    kind: str  # dash | semicolon | exclamation | spacing
    count: int


def _split_protected(line: str) -> list[tuple[bool, str]]:
    """Alternate (protected, text) chunks; protected chunks are copied through untouched."""
    parts: list[tuple[bool, str]] = []
    pos = 0
    for m in _PROTECTED.finditer(line):
        if m.start() > pos:
            parts.append((False, line[pos : m.start()]))
        parts.append((True, m.group(0)))
        pos = m.end()
    if pos < len(line):
        parts.append((False, line[pos:]))
    return parts


def _fix_dashes(s: str) -> tuple[str, int]:
    """Em dashes and spaced en dashes. A pair inside one sentence becomes commas; a single dash
    becomes a comma before a lowercase continuation and a full stop before a capital."""
    n = 0
    dash = re.compile("\\s*(?:\u2014|\\s\u2013\\s|\\s--\\s)\\s*")  # em dash, spaced en dash, --
    sentences = re.split(r"(?<=[.!?])\s+", s)
    out: list[str] = []
    for sent in sentences:
        hits = list(dash.finditer(sent))
        if not hits:
            out.append(sent)
            continue
        n += len(hits)
        if len(hits) >= 2:
            sent = dash.sub(", ", sent)
        else:
            m = hits[0]
            after = sent[m.end() :]
            before = sent[: m.start()].rstrip()
            if after[:1].isupper() and len(_WORD.findall(before)) >= 3 and len(_WORD.findall(after)) >= 3:
                sent = before.rstrip(",;:") + ". " + after
            else:
                sent = before + ", " + after
        out.append(sent)
    return " ".join(out), n


def _fix_semicolons(s: str) -> tuple[str, int]:
    """`clause; clause` with at least four words on each side becomes two sentences."""
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        before, after = m.group(1), m.group(2)
        if len(_WORD.findall(before)) < 4 or len(_WORD.findall(after)) < 4:
            return m.group(0)
        n += 1
        return f"{before.rstrip()}. {after[0].upper()}{after[1:]}"

    pattern = re.compile(r"([^.;!?]+);\s+([a-z][^.;!?]*)")
    prev = None
    while prev != s:
        prev = s
        s = pattern.sub(repl, s, count=1)
    return s, n


def _fix_exclamations(s: str) -> tuple[str, int]:
    new = re.sub(r"!(?=\s|$)", ".", s)
    return new, s.count("!") - new.count("!")


def _fix_spacing(s: str) -> tuple[str, int]:
    new = re.sub(r"[ \t]{2,}", " ", s)
    new = re.sub(r" +([,.;:])", r"\1", new)
    return new, int(new != s)


def mechanical_pass(text: str) -> tuple[str, list[Change]]:
    """Return the cleaned text and a count of what changed, by kind."""
    totals = {"dash": 0, "semicolon": 0, "exclamation": 0, "spacing": 0}
    lines = text.split("\n")
    in_code = False
    for i, raw in enumerate(lines):
        if raw.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or not _is_prose_line(raw) or raw.lstrip().startswith(("-", "*", "1.")):
            continue
        rebuilt: list[str] = []
        for protected, chunk in _split_protected(raw):
            if protected:
                rebuilt.append(chunk)
                continue
            chunk, d = _fix_dashes(chunk)
            chunk, sc = _fix_semicolons(chunk)
            chunk, ex = _fix_exclamations(chunk)
            chunk, sp = _fix_spacing(chunk)
            totals["dash"] += d
            totals["semicolon"] += sc
            totals["exclamation"] += ex
            totals["spacing"] += sp
            rebuilt.append(chunk)
        lines[i] = "".join(rebuilt)
    return "\n".join(lines), [Change(k, v) for k, v in totals.items() if v]


def describe(changes: list[Change]) -> str:
    names = {"dash": "dash", "semicolon": "semicolon", "exclamation": "exclamation mark", "spacing": "spacing fix"}
    parts = [f"{c.count} {names[c.kind]}{'' if c.count == 1 else 's' if c.kind != 'dash' else 'es'}" for c in changes]
    return ", ".join(parts)
