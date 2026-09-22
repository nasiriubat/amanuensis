"""LaTeX source to Markdown.

Uses pandoc when it is installed (the Docker image has it). Otherwise falls back to a
regex converter that keeps what an LLM needs: headings, paragraphs, citations as
[@key], emphasis, lists, equations, and figure/table captions.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_COMMENT = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
_INPUT = re.compile(r"\\(?:input|include|subfile)\{([^}]+)\}")


def strip_comments(tex: str) -> str:
    return _COMMENT.sub("", tex)


def find_main_tex(root: Path) -> Path | None:
    """The .tex file that has \\documentclass, preferring one with \\begin{document}."""
    candidates = []
    for p in root.rglob("*.tex"):
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "\\documentclass" in head:
            score = 2 if "\\begin{document}" in head else 1
            candidates.append((score, -len(str(p)), p))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]


def flatten(main: Path, _seen: set[Path] | None = None) -> str:
    """Inline \\input and \\include recursively."""
    seen = _seen or set()
    if main in seen:
        return ""
    seen.add(main)
    tex = strip_comments(main.read_text(encoding="utf-8", errors="ignore"))
    base = main.parent

    def repl(m: re.Match) -> str:
        name = m.group(1).strip()
        for cand in (base / name, base / f"{name}.tex"):
            if cand.is_file():
                return "\n" + flatten(cand, seen) + "\n"
        return ""

    return _INPUT.sub(repl, tex)


def find_bib_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.bib"))


# ------------------------------------------------------------------ pandoc path


def pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


def latex_to_markdown_pandoc(tex: str) -> str | None:
    try:
        r = subprocess.run(
            ["pandoc", "-f", "latex", "-t", "gfm", "--wrap=none", "--markdown-headings=atx"],
            input=tex,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return r.stdout


# ------------------------------------------------------------------ regex fallback

_ENV_DROP = [
    "tikzpicture",
    "algorithmic",
    "lstlisting",
    "minted",
    "verbatim",
    "comment",
    "thebibliography",
    "CCSXML",
]
# Commands whose arguments are layout or macro definitions, never prose. Dropped with their arguments.
_CMD_DROP = [
    "newcommand",
    "renewcommand",
    "providecommand",
    "newenvironment",
    "renewenvironment",
    "DeclareMathOperator",
    "newtheorem",
    "theoremstyle",
    "usepackage",
    "documentclass",
    "definecolor",
    "newcolumntype",
    "setlength",
    "addtolength",
    "setcounter",
    "addtocounter",
    "vspace",
    "hspace",
    "fontsize",
    "includegraphics",
    "resizebox",
    "scalebox",
    "rotatebox",
    "bibliographystyle",
    "bibliography",
    "pagestyle",
    "thispagestyle",
    "author",
    "affiliation",
    "affil",
    "institute",
    "email",
    "orcid",
    "date",
    "thanks",
    "keywords",
    "ccsdesc",
    "acmConference",
    "acmYear",
    "copyrightyear",
    "acmDOI",
    "acmISBN",
    "acmPrice",
    "acmBooktitle",
    "settopmatter",
    "titlenote",
    "authornote",
    "hypersetup",
    "lstset",
    "captionsetup",
    "graphicspath",
    "input",
    "include",
    "cline",
    "hline",
    "toprule",
    "midrule",
    "bottomrule",
    "multicolumn",
    "multirow",
    "label",
    "index",
    "glossary",
    "phantom",
    "vphantom",
    "hphantom",
]
_SECTION = re.compile(r"\\(section|subsection|subsubsection|paragraph)\*?\s*\{")


def _drop_cmd(tex: str, cmd: str) -> str:
    """Remove \\cmd, its optional args and every following brace group."""
    out = []
    i = 0
    pat = re.compile(r"\\" + cmd + r"\*?(?![a-zA-Z])")
    while True:
        m = pat.search(tex, i)
        if not m:
            out.append(tex[i:])
            break
        out.append(tex[i : m.start()])
        j = m.end()
        while j < len(tex):
            if tex[j] == "[":
                k = tex.find("]", j)
                if k == -1:
                    break
                j = k + 1
            elif tex[j] == "{":
                _, j = _balanced(tex, j)
            elif tex[j] in " \t":
                j += 1
            else:
                break
        i = j
    return "".join(out)


def _balanced(s: str, start: int) -> tuple[str, int]:
    """Return content of the brace group starting at s[start] == '{' and index after it."""
    depth = 0
    i = start
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1 : i], i + 1
        i += 1
    return s[start + 1 :], len(s)


def _replace_cmd(tex: str, cmd: str, fmt) -> str:
    """Replace \\cmd{arg} (with balanced braces) using fmt(arg)."""
    out = []
    i = 0
    pat = re.compile(r"\\" + cmd + r"\*?\s*(\[[^\]]*\])?\s*\{")
    while True:
        m = pat.search(tex, i)
        if not m:
            out.append(tex[i:])
            break
        out.append(tex[i : m.start()])
        arg, end = _balanced(tex, m.end() - 1)
        out.append(fmt(arg))
        i = end
    return "".join(out)


def _captions(tex: str, env: str, label: str) -> str:
    """Replace figure/table environments with their caption line."""
    pat = re.compile(r"\\begin\{" + env + r"\*?\}(.*?)\\end\{" + env + r"\*?\}", re.DOTALL)
    counter = [0]

    def repl(m: re.Match) -> str:
        counter[0] += 1
        body = m.group(1)
        cm = re.search(r"\\caption\s*(\[[^\]]*\])?\s*\{", body)
        cap = ""
        if cm:
            cap, _ = _balanced(body, cm.end() - 1)
        cap = re.sub(r"\s+", " ", cap).strip()
        return f"\n\n> **{label} {counter[0]}.** {cap}\n\n"

    return pat.sub(repl, tex)


def latex_to_markdown_fallback(tex: str) -> str:
    body = tex
    m = re.search(r"\\begin\{document\}", body)
    if m:
        body = body[m.end() :]
    body = re.sub(r"\\end\{document\}.*", "", body, flags=re.DOTALL)

    # Title, abstract
    body = _replace_cmd(body, "title", lambda a: f"\n# {a}\n")
    body = re.sub(r"\\maketitle", "", body)
    body = re.sub(r"\\begin\{abstract\}", "\n## Abstract\n\n", body)
    body = re.sub(r"\\end\{abstract\}", "\n", body)

    for env in _ENV_DROP:
        body = re.sub(r"\\begin\{" + env + r"\*?\}.*?\\end\{" + env + r"\*?\}", "", body, flags=re.DOTALL)
    for env, label in (
        ("figure", "Figure"),
        ("wrapfigure", "Figure"),
        ("subfigure", "Figure"),
        ("table", "Table"),
        ("wraptable", "Table"),
        ("algorithm", "Algorithm"),
        ("listing", "Listing"),
    ):
        body = _captions(body, env, label)
    for cmd in _CMD_DROP:
        body = _drop_cmd(body, cmd)

    # Headings
    def heading(level: int):
        return lambda a: "\n" + "#" * level + " " + re.sub(r"\s+", " ", a).strip() + "\n"

    body = _replace_cmd(body, "section", heading(2))
    body = _replace_cmd(body, "subsection", heading(3))
    body = _replace_cmd(body, "subsubsection", heading(4))
    body = _replace_cmd(body, "paragraph", lambda a: f"\n**{a.strip()}** ")

    # Citations and refs
    body = re.sub(
        r"\\(?:cite[tp]?|citep|citet|citeauthor|citeyear|parencite|textcite|autocite)\*?\s*(?:\[[^\]]*\])*\s*\{([^}]+)\}",
        lambda m: "[" + "; ".join("@" + k.strip() for k in m.group(1).split(",")) + "]",
        body,
    )
    body = re.sub(r"\\(?:ref|cref|Cref|autoref|eqref|pageref)\{([^}]+)\}", lambda m: f"[{m.group(1)}]", body)
    body = re.sub(r"\\label\{[^}]*\}", "", body)
    body = re.sub(r"\\footnote\s*\{", " (footnote: {", body)  # crude but keeps text

    # Emphasis
    for cmd, wrap in (("textbf", "**"), ("emph", "*"), ("textit", "*"), ("texttt", "`")):
        body = _replace_cmd(body, cmd, lambda a, w=wrap: f"{w}{a}{w}")
    body = _replace_cmd(body, "url", lambda a: f"<{a}>")
    body = _replace_cmd(body, "href", lambda a: a)

    # Lists
    body = re.sub(r"\\begin\{(itemize|enumerate|description)\}(\[[^\]]*\])?", "\n", body)
    body = re.sub(r"\\end\{(itemize|enumerate|description)\}", "\n", body)
    body = re.sub(r"\\item\s*(\[[^\]]*\])?\s*", "\n- ", body)

    # Equations
    body = re.sub(r"\\begin\{(equation|align|gather|multline)\*?\}", "\n$$\n", body)
    body = re.sub(r"\\end\{(equation|align|gather|multline)\*?\}", "\n$$\n", body)
    body = re.sub(r"\\\[", "\n$$\n", body)
    body = re.sub(r"\\\]", "\n$$\n", body)

    # Leftover commands: keep their argument text, drop the command name
    for _ in range(3):
        body = re.sub(r"\\[a-zA-Z]+\*?\s*(\[[^\]]*\])?\s*\{([^{}]*)\}", r"\2", body)
    body = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", body)
    body = body.replace("~", " ").replace("``", '"').replace("''", '"').replace("--", "-")
    body = re.sub(r"[{}]", "", body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n"


def latex_to_markdown(tex: str) -> tuple[str, str]:
    """Returns (markdown, method)."""
    if pandoc_available():
        md = latex_to_markdown_pandoc(tex)
        if md:
            return md, "pandoc"
    return latex_to_markdown_fallback(tex), "regex"
