"""Deterministic prose statistics. Free, instant, and a good sanity check on the LLM's impressions."""

from __future__ import annotations

import re
from collections import Counter

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[\(])")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_FIRST_PERSON = re.compile(r"\b(we|our|us)\b", re.I)
_PASSIVE = re.compile(r"\b(is|are|was|were|be|been|being)\s+(\w+ed|\w+en)\b", re.I)


def prose_only(md: str) -> str:
    md = re.sub(r"^#.*$", "", md, flags=re.MULTILINE)
    md = re.sub(r"```.*?```", "", md, flags=re.DOTALL)
    md = re.sub(r"\$\$.*?\$\$", "", md, flags=re.DOTALL)
    md = re.sub(r"^\s*[-*]\s+.*$", "", md, flags=re.MULTILINE)
    md = re.sub(r"^>.*$", "", md, flags=re.MULTILINE)
    md = re.sub(r"\[@[^\]]+\]", "", md)
    md = re.sub(r"\[[^\]]{1,40}\]", "", md)
    return md


def text_stats(md: str) -> dict:
    text = prose_only(md)
    sents = [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) > 10]
    if not sents:
        return {"sentences": 0}
    lengths = [len(_WORD.findall(s)) for s in sents]
    words = sum(lengths)
    openers = Counter(" ".join(_WORD.findall(s)[:2]).lower() for s in sents if _WORD.findall(s))
    paras = [p for p in re.split(r"\n\s*\n", text) if len(p.split()) > 20]
    return {
        "sentences": len(sents),
        "words": words,
        "avg_sentence_words": round(words / len(sents), 1),
        "share_over_30_words": round(sum(1 for n in lengths if n > 30) / len(sents), 2),
        "share_under_12_words": round(sum(1 for n in lengths if n < 12) / len(sents), 2),
        "avg_paragraph_words": round(sum(len(p.split()) for p in paras) / len(paras), 1) if paras else None,
        "first_person_per_100_sentences": round(100 * len(_FIRST_PERSON.findall(text)) / len(sents), 1),
        "passive_per_100_sentences": round(100 * len(_PASSIVE.findall(text)) / len(sents), 1),
        "em_dashes": text.count("—") + text.count(" - "),
        "semicolons": text.count(";"),
        "questions": sum(1 for s in sents if s.endswith("?")),
        "top_openers": [f"{k} ({v})" for k, v in openers.most_common(8)],
    }


def merge_stats(all_stats: list[dict]) -> dict:
    valid = [s for s in all_stats if s.get("sentences")]
    if not valid:
        return {"papers": 0}
    n = len(valid)
    total_sents = sum(s["sentences"] for s in valid)

    def wavg(key):
        vals = [(s[key], s["sentences"]) for s in valid if s.get(key) is not None]
        return round(sum(v * w for v, w in vals) / sum(w for _, w in vals), 2) if vals else None

    openers = Counter()
    for s in valid:
        for item in s.get("top_openers", []):
            k, v = item.rsplit(" (", 1)
            openers[k] += int(v.rstrip(")"))
    return {
        "papers": n,
        "sentences": total_sents,
        "avg_sentence_words": wavg("avg_sentence_words"),
        "share_over_30_words": wavg("share_over_30_words"),
        "share_under_12_words": wavg("share_under_12_words"),
        "avg_paragraph_words": wavg("avg_paragraph_words"),
        "first_person_per_100_sentences": wavg("first_person_per_100_sentences"),
        "passive_per_100_sentences": wavg("passive_per_100_sentences"),
        "em_dashes_total": sum(s.get("em_dashes", 0) for s in valid),
        "semicolons_total": sum(s.get("semicolons", 0) for s in valid),
        "questions_total": sum(s.get("questions", 0) for s in valid),
        "top_openers": [f"{k} ({v})" for k, v in openers.most_common(10)],
    }
