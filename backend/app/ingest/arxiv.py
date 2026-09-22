"""arXiv: metadata, LaTeX source, PDF fallback."""

from __future__ import annotations

import gzip
import io
import re
import tarfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import httpx

ARXIV_ID = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf|e-print)/)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)", re.I
)
_NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
_UA = "paper-writer/0.1 (self-hosted research tool; contact: admin)"


def parse_arxiv_id(text: str) -> str | None:
    text = text.strip()
    m = ARXIV_ID.search(text)
    if not m:
        return None
    return m.group(1).replace(".pdf", "")


@dataclass
class ArxivMeta:
    id: str
    title: str
    authors: list[str]
    abstract: str
    published: str
    updated: str
    categories: list[str] = field(default_factory=list)
    comment: str | None = None
    journal_ref: str | None = None
    doi: str | None = None

    @property
    def year(self) -> int | None:
        return int(self.published[:4]) if self.published else None


async def _get(
    client: httpx.AsyncClient, url: str, *, params: dict | None = None, timeout: float = 60
) -> httpx.Response:
    """GET with retries. arXiv occasionally answers 406 or 429 to well-formed requests; a short wait fixes it."""
    import asyncio

    delays = (0, 2, 6, 12)
    last: Exception | None = None
    for delay in delays:
        if delay:
            await asyncio.sleep(delay)
        try:
            r = await client.get(url, params=params, timeout=timeout, follow_redirects=True)
        except httpx.TransportError as e:
            last = e
            continue
        if r.status_code in (406, 429, 500, 502, 503, 504):
            last = httpx.HTTPStatusError(f"{r.status_code} from arXiv", request=r.request, response=r)
            continue
        r.raise_for_status()
        return r
    raise last or RuntimeError("arXiv request failed")


async def fetch_meta(arxiv_id: str, client: httpx.AsyncClient) -> ArxivMeta:
    r = await _get(client, "https://export.arxiv.org/api/query", params={"id_list": arxiv_id}, timeout=30)
    root = ET.fromstring(r.text)
    entry = root.find("a:entry", _NS)
    if entry is None or entry.find("a:title", _NS) is None:
        raise ValueError(f"arXiv has no entry for {arxiv_id}")
    title = re.sub(r"\s+", " ", entry.findtext("a:title", "", _NS)).strip()
    if title.lower() == "error":
        raise ValueError(f"arXiv returned an error for {arxiv_id}")
    authors = [a.findtext("a:name", "", _NS).strip() for a in entry.findall("a:author", _NS)]
    cats = [c.attrib.get("term", "") for c in entry.findall("a:category", _NS)]
    return ArxivMeta(
        id=arxiv_id,
        title=title,
        authors=authors,
        abstract=re.sub(r"\s+", " ", entry.findtext("a:summary", "", _NS)).strip(),
        published=entry.findtext("a:published", "", _NS),
        updated=entry.findtext("a:updated", "", _NS),
        categories=cats,
        comment=entry.findtext("arxiv:comment", None, _NS),
        journal_ref=entry.findtext("arxiv:journal_ref", None, _NS),
        doi=entry.findtext("arxiv:doi", None, _NS),
    )


async def fetch_source(arxiv_id: str, dest: Path, client: httpx.AsyncClient) -> str:
    """Download the e-print into dest. Returns 'latex' when a .tex tree was unpacked, 'pdf' otherwise.

    arXiv serves either a gzipped tarball, a single gzipped .tex, or a PDF when no
    source is available.
    """
    r = await _get(client, f"https://arxiv.org/e-print/{arxiv_id}", timeout=120)
    data = r.content
    dest.mkdir(parents=True, exist_ok=True)
    ctype = r.headers.get("content-type", "")

    if data[:4] == b"%PDF" or "pdf" in ctype:
        (dest / "source.pdf").write_bytes(data)
        return "pdf"

    try:
        raw = gzip.decompress(data)
    except OSError:
        raw = data

    if raw[:4] == b"%PDF":
        (dest / "source.pdf").write_bytes(raw)
        return "pdf"

    src_dir = dest / "src"
    src_dir.mkdir(exist_ok=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as tar:
            _safe_extract(tar, src_dir)
        return "latex"
    except tarfile.TarError:
        pass
    # single .tex file
    (src_dir / "main.tex").write_bytes(raw)
    return "latex"


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    dest_resolved = dest.resolve()
    for member in tar.getmembers():
        if member.issym() or member.islnk():
            continue
        target = (dest / member.name).resolve()
        if dest_resolved not in target.parents and target != dest_resolved:
            continue
        if member.size > 50 * 1024 * 1024:
            continue
        tar.extract(member, dest, filter="data")


async def fetch_pdf(arxiv_id: str, dest: Path, client: httpx.AsyncClient) -> Path:
    r = await _get(client, f"https://arxiv.org/pdf/{arxiv_id}", timeout=120)
    dest.mkdir(parents=True, exist_ok=True)
    p = dest / "source.pdf"
    p.write_bytes(r.content)
    return p


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": _UA, "Accept": "*/*"}, follow_redirects=True)
