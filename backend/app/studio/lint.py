"""Deterministic prose lint (SPEC 4.11). No LLM. Reads rules from the house style file.

Findings carry 1-based line numbers so the editor can mark them inline.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_CITE = re.compile(r"\[@([^\]\s;]+)(?:;\s*@([^\]\s;]+))*\]")
_CITE_KEYS = re.compile(r"@([^\]\s;]+)")
_NEEDS = re.compile(r"\[(NEEDS|CITE):\s*([^\]]+)\]")
_OPENERS = ("furthermore", "moreover", "additionally", "however", "in addition")

LONG_SENTENCE = 35


@dataclass
class Finding:
    line: int
    kind: str  # banned | dash | semicolon | long | opener | citation | needs | exclamation | question
    severity: str  # error | warning | info
    message: str
    excerpt: str = ""


def banned_phrases(house_style: str) -> list[str]:
    """Comma separated list under '## Banned words and phrases'."""
    m = re.search(r"^## Banned words and phrases\s*\n(.*?)(?=^## |\Z)", house_style, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    # drop the explanatory sentence(s) before the list: keep from the first line that has a comma-separated run
    items: list[str] = []
    for chunk in re.split(r",|\n", body):
        c = chunk.strip().strip(".").strip()
        if not c or c.endswith(":") or len(c.split()) > 6 or c.lower().startswith(("never", "they are")):
            continue
        c = re.sub(r"\s*\([^)]*\)", "", c).strip()
        if c and c.lower() not in items:
            items.append(c.lower())
    return items


def _is_prose_line(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith(("#", "```", "|", "> **", "$$", "![")) and not re.match(r"^\s*\[NEEDS:", s)


def lint(text: str, house_style: str, known_keys: set[str] | None = None) -> list[dict]:
    known = known_keys or set()
    phrases = banned_phrases(house_style)
    findings: list[Finding] = []
    prev_opener: str | None = None
    in_code = False

    for i, raw in enumerate(text.split("\n"), start=1):
        if raw.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        for m in _NEEDS.finditer(raw):
            kind = "needs" if m.group(1) == "NEEDS" else "citation"
            findings.append(Finding(i, kind, "warning", f"Open item: {m.group(2).strip()}", m.group(0)))
        if not _is_prose_line(raw):
            continue
        line = raw
        low = line.lower()

        for m in _CITE.finditer(line):
            for key in _CITE_KEYS.findall(m.group(0)):
                if key not in known:
                    findings.append(
                        Finding(i, "citation", "error", f"Citation key @{key} is not a verified reference", m.group(0))
                    )

        if "\u2014" in line or " \u2013 " in line:
            findings.append(
                Finding(
                    i,
                    "dash",
                    "warning",
                    "Dash used as sentence punctuation; use a comma, full stop or parentheses",
                    "\u2014",
                )
            )
        if ";" in re.sub(r"\[@[^\]]*\]", "", line):
            findings.append(Finding(i, "semicolon", "info", "Semicolon joining clauses; consider two sentences", ";"))
        if "!" in line:
            findings.append(Finding(i, "exclamation", "warning", "Exclamation mark", "!"))

        for phrase in phrases:
            if re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", low):
                findings.append(Finding(i, "banned", "warning", f"Banned phrase: “{phrase}”", phrase))

        sentences = [s for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\[@[^\]]*\]", "", line)) if s.strip()]
        for s in sentences:
            n = len(_WORD.findall(s))
            if n > LONG_SENTENCE:
                findings.append(
                    Finding(
                        i,
                        "long",
                        "info",
                        f"{n}-word sentence; aim for under {LONG_SENTENCE}",
                        s[:60] + ("…" if len(s) > 60 else ""),
                    )
                )
            if s.rstrip().endswith("?"):
                findings.append(Finding(i, "question", "info", "Rhetorical question", s[:60]))
        first = _WORD.findall(line)
        if first:
            opener = first[0].lower()
            two = " ".join(w.lower() for w in first[:2])
            hit = opener if opener in _OPENERS else two if two in _OPENERS else None
            if hit and prev_opener == hit:
                findings.append(Finding(i, "opener", "info", f"Two paragraphs in a row open with “{hit}”", hit))
            prev_opener = hit if hit else None

    return [asdict(f) for f in findings]


def summarize(findings: list[dict]) -> dict:
    out = {"errors": 0, "warnings": 0, "info": 0}
    for f in findings:
        out[f["severity"] + "s" if f["severity"] != "info" else "info"] += 1
    return out
