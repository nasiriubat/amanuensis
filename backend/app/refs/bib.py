"""Small BibTeX reader and writer. Enough for real-world .bib files; no LaTeX macro expansion."""

from __future__ import annotations

import re

_ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)


def _read_value(s: str, i: int) -> tuple[str, int]:
    """Parse a field value starting at s[i]: {…}, "…", number, or a bare macro/concatenation."""
    n = len(s)
    while i < n and s[i] in " \t\r\n":
        i += 1
    if i >= n:
        return "", i
    if s[i] == "{":
        depth = 0
        j = i
        while j < n:
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    return s[i + 1 : j], j + 1
            j += 1
        return s[i + 1 :], n
    if s[i] == '"':
        j = i + 1
        while j < n and s[j] != '"':
            j += 1
        return s[i + 1 : j], j + 1
    j = i
    while j < n and s[j] not in ",}\n":
        j += 1
    return s[i:j].strip(), j


def parse_bib(text: str) -> list[dict]:
    """Return [{bibtype, key, fields: {name: value}}]."""
    entries = []
    for m in _ENTRY.finditer(text):
        bibtype = m.group(1).lower()
        if bibtype in ("comment", "preamble", "string"):
            continue
        key = m.group(2)
        i = m.end()
        fields: dict[str, str] = {}
        n = len(text)
        while i < n:
            while i < n and text[i] in " \t\r\n,":
                i += 1
            if i >= n or text[i] == "}":
                break
            fm = re.match(r"([\w\-:]+)\s*=", text[i:])
            if not fm:
                break
            name = fm.group(1).lower()
            val, i = _read_value(text, i + fm.end())
            fields[name] = re.sub(r"\s+", " ", val.replace("\n", " ")).strip()
        entries.append({"bibtype": bibtype, "key": key, "fields": fields})
    return entries


def _clean(s: str) -> str:
    return re.sub(r"[{}]", "", s or "").strip()


def entry_to_record(e: dict) -> dict:
    f = e["fields"]
    authors = [a.strip() for a in re.split(r"\s+and\s+", _clean(f.get("author", ""))) if a.strip()]
    year = None
    m = re.search(r"\d{4}", f.get("year", "") or f.get("date", ""))
    if m:
        year = int(m.group(0))
    venue = _clean(f.get("journal") or f.get("booktitle") or f.get("publisher") or f.get("howpublished") or "")
    arxiv = None
    if f.get("eprint") and (
        "arxiv" in (f.get("archiveprefix", "") + f.get("eprinttype", "")).lower()
        or re.match(r"\d{4}\.\d{4,5}", f["eprint"])
    ):
        arxiv = f["eprint"]
    return {
        "key": e["key"],
        "title": _clean(f.get("title", "")),
        "authors": authors,
        "year": year,
        "venue": venue or None,
        "doi": _clean(f.get("doi", "")) or None,
        "url": _clean(f.get("url", "")) or None,
        "arxiv_id": arxiv,
        "abstract": _clean(f.get("abstract", "")) or None,
        "bibtype": e["bibtype"],
        "bib_fields": f,
    }


def _esc(s: str) -> str:
    return (s or "").replace("{", "").replace("}", "").replace("&", "\\&").replace("%", "\\%")


def record_to_bibtex(r: dict) -> str:
    fields = dict(r.get("bib_fields") or {})
    if not fields:
        fields["title"] = "{" + _esc(r.get("title", "")) + "}"
        if r.get("authors"):
            fields["author"] = " and ".join(_esc(a) for a in r["authors"])
        if r.get("year"):
            fields["year"] = str(r["year"])
        if r.get("venue"):
            fields[
                "journal"
                if r.get("bibtype") == "article"
                else "booktitle"
                if r.get("bibtype") == "inproceedings"
                else "howpublished"
            ] = _esc(r["venue"])
        if r.get("doi"):
            fields["doi"] = r["doi"]
        if r.get("url"):
            fields["url"] = r["url"]
        if r.get("arxiv_id"):
            fields["eprint"] = r["arxiv_id"]
            fields["archiveprefix"] = "arXiv"
    lines = [f"@{r.get('bibtype') or 'misc'}{{{r['key']},"]
    for k, v in fields.items():
        v = str(v)
        if not (v.startswith("{") and v.endswith("}")) and not v.isdigit():
            v = "{" + v + "}"
        lines.append(f"  {k} = {v},")
    lines.append("}")
    return "\n".join(lines)


def make_key(authors: list[str], year: int | None, title: str, taken: set[str]) -> str:
    surname = "anon"
    if authors:
        first = authors[0]
        surname = first.split(",")[0].strip() if "," in first else first.split()[-1]
    surname = re.sub(r"[^a-z]", "", surname.lower()) or "anon"
    stop = {"a", "an", "the", "on", "of", "for", "and", "in", "to", "with", "towards", "toward", "from", "by", "via"}
    word = next((w for w in re.findall(r"[a-z]+", title.lower()) if w not in stop and len(w) > 2), "paper")
    base = f"{surname}{year or ''}{word}"
    key = base
    suffix = ord("a")
    while key in taken:
        key = f"{base}{chr(suffix)}"
        suffix += 1
    return key
