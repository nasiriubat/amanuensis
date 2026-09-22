from app.ingest.arxiv import parse_arxiv_id
from app.ingest.extract import sections_of
from app.ingest.latex import latex_to_markdown_fallback
from app.learn.context import budget_markdown, sample_for_style
from app.learn.stats import merge_stats, text_stats

TEX = r"""
\documentclass{article}
\newcommand{\tool}{Tender Scout}
\begin{document}
\title{A Tool Paper}
\author{Someone}
\maketitle
\vspace{-2em}
\begin{abstract}
We present a tool. It helps people~\cite{smith2020, jones21}.
\end{abstract}
\section{Introduction}
\label{sec:intro}
Tenders are hard \textbf{to find}. See Section~\ref{sec:design} and Figure~\ref{fig:arch}.
\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{arch.pdf}
\caption{The architecture of the system.}
\label{fig:arch}
\end{figure}
\begin{itemize}
\item First point
\item Second point
\end{itemize}
\section{Design}
\label{sec:design}
The \emph{matcher} uses an LLM\footnote{A large language model.}.
\begin{equation}
y = f(x)
\end{equation}
\section{References}
\bibliographystyle{plain}
\bibliography{refs}
\end{document}
"""


def test_arxiv_id_parsing():
    assert parse_arxiv_id("2405.15793") == "2405.15793"
    assert parse_arxiv_id("https://arxiv.org/abs/2405.15793v2") == "2405.15793v2"
    assert parse_arxiv_id("https://arxiv.org/pdf/2405.15793") == "2405.15793"
    assert parse_arxiv_id("arxiv.org/abs/cs/0112017") == "cs/0112017"
    assert parse_arxiv_id("not an id") is None


def test_latex_fallback_conversion():
    md = latex_to_markdown_fallback(TEX)
    assert "# A Tool Paper" in md
    assert "## Abstract" in md and "## Introduction" in md and "## Design" in md
    assert "[@smith2020; @jones21]" in md
    assert "**to find**" in md and "*matcher*" in md
    assert "> **Figure 1.** The architecture of the system." in md
    assert "- First point" in md and "- Second point" in md
    assert "$$" in md and "y = f(x)" in md
    # preamble junk and layout commands are gone
    assert "newcommand" not in md and "-2em" not in md and "includegraphics" not in md and "arch.pdf" not in md
    assert "Someone" not in md  # \author dropped
    assert "\\" not in md.replace("\\\\", "")


def test_sections_and_budget():
    md = latex_to_markdown_fallback(TEX)
    secs = sections_of(md)
    titles = [s["title"] for s in secs]
    assert titles[:4] == ["A Tool Paper", "Abstract", "Introduction", "Design"]

    long_md = (
        "# T\n\n## Intro\n\n"
        + ("Intro sentence. " * 400)
        + "\n\n## Body\n\n"
        + ("Body sentence. " * 1500)
        + "\n\n## References\n\n"
        + ("ref " * 800)
    )
    small = budget_markdown(long_md, 6000)
    assert len(small) <= 6000 * 1.15
    assert "## Intro" in small and "## Body" in small
    assert "[references omitted]" in small
    assert "ref ref ref" not in small
    # proportional: body gets more than intro
    assert small.index("## Body") - small.index("## Intro") < len(small) - small.index("## Body")

    sample = sample_for_style(long_md, 3000)
    assert len(sample) <= 3000 * 1.3
    assert "Intro sentence" in sample


def test_text_stats():
    para = "We built a tool. It is used by many people in Finland. Does it work? We think so; results are shown."
    md = f"## Intro\n\n{para}\n\n" * 5
    st = text_stats(md)
    assert st["sentences"] >= 15
    assert st["questions"] == 5
    assert st["semicolons"] == 5
    assert st["first_person_per_100_sentences"] > 0
    merged = merge_stats([st, st])
    assert merged["papers"] == 2
    assert merged["avg_sentence_words"] == st["avg_sentence_words"]
