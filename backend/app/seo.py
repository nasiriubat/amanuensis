"""Server-side head tags for the SPA so crawlers and link previews see real titles and descriptions."""

from __future__ import annotations

import html
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Page

PRIVATE_PREFIXES = ("login", "library", "profiles", "projects", "admin", "account")

_MD_STRIP = re.compile(r"[#*_>`\[\]()!|]+|(?<!\w)-|-(?!\w)|\n+")


def _excerpt(markdown: str, limit: int = 160) -> str:
    for para in markdown.split("\n\n"):
        t = para.strip()
        if not t or t.startswith("#") or t.startswith("!["):
            continue
        t = _MD_STRIP.sub(" ", t)
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            return t[: limit - 1].rsplit(" ", 1)[0] + "…" if len(t) > limit else t
    return ""


def _base_url() -> str:
    return get_settings().app_url.rstrip("/")


def head_for(path: str, site: dict, db: Session) -> dict:
    """Title, description, canonical, robots and JSON-LD for one path."""
    name = site["seo"].get("title") or site["name"]
    tagline = site.get("tagline") or ""
    description = site["seo"].get("description") or tagline
    clean = path.strip("/")
    private = clean.split("/", 1)[0] in PRIVATE_PREFIXES
    robots = "noindex, nofollow" if private or not site["seo"].get("index", True) else "index, follow"
    title = f"{name} · {tagline}" if tagline else name
    ld: dict | None = None
    if clean.startswith("p/"):
        slug = clean[2:].split("/", 1)[0]
        page = db.scalar(select(Page).where(Page.slug == slug, Page.published.is_(True)))
        if page:
            title = f"{page.title} · {name}"
            description = _excerpt(page.content) or description
            ld = {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "name": page.title,
                "description": description,
                "url": f"{_base_url()}/p/{page.slug}",
            }
        else:
            robots = "noindex, nofollow"
    elif clean == "":
        ld = {
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": site["name"],
            "applicationCategory": "Productivity",
            "operatingSystem": "Web",
            "description": description,
            "url": _base_url() + "/",
        }
    elif clean == "landing":
        title = f"How it works · {name}"
    elif private:
        label = {
            "login": "Sign in",
            "library": "Library",
            "account": "Account",
            "admin": "Settings",
            "projects": "Project",
            "profiles": "Author profile",
        }[clean.split("/", 1)[0]]
        title = f"{label} · {name}"
    return {
        "title": title,
        "description": description,
        "canonical": f"{_base_url()}/{clean}" if not private else "",
        "robots": robots,
        "og_image": site["seo"].get("og_image") or "",
        "keywords": site["seo"].get("keywords") or "",
        "site_name": site["name"],
        "ld": ld,
    }


def render_head(meta: dict) -> str:
    e = html.escape
    parts = [f"<title>{e(meta['title'])}</title>"]
    if meta["description"]:
        parts.append(f'<meta name="description" content="{e(meta["description"])}">')
    if meta["keywords"]:
        parts.append(f'<meta name="keywords" content="{e(meta["keywords"])}">')
    parts.append(f'<meta name="robots" content="{e(meta["robots"])}">')
    if meta["canonical"]:
        parts.append(f'<link rel="canonical" href="{e(meta["canonical"])}">')
    parts.append(f'<meta property="og:site_name" content="{e(meta["site_name"])}">')
    parts.append(f'<meta property="og:title" content="{e(meta["title"])}">')
    parts.append('<meta property="og:type" content="website">')
    if meta["description"]:
        parts.append(f'<meta property="og:description" content="{e(meta["description"])}">')
    if meta["canonical"]:
        parts.append(f'<meta property="og:url" content="{e(meta["canonical"])}">')
    if meta["og_image"]:
        parts.append(f'<meta property="og:image" content="{e(meta["og_image"])}">')
        parts.append('<meta name="twitter:card" content="summary_large_image">')
    else:
        parts.append('<meta name="twitter:card" content="summary">')
    if meta["ld"]:
        parts.append(
            '<script type="application/ld+json">'
            + json.dumps(meta["ld"], ensure_ascii=False).replace("</", "<\\/")
            + "</script>"
        )
    return "\n    ".join(parts)


_TITLE_RE = re.compile(r"<title>.*?</title>", re.DOTALL)


def inject(index_html: str, meta: dict) -> str:
    head = render_head(meta)
    out = _TITLE_RE.sub("", index_html, count=1)
    return out.replace("</head>", f"    {head}\n  </head>", 1)


def sitemap(site: dict, db: Session) -> str:
    base = _base_url()
    urls = [f"{base}/", f"{base}/landing"]
    for p in db.scalars(select(Page).where(Page.published.is_(True)).order_by(Page.nav_order)).all():
        urls.append(f"{base}/p/{p.slug}")
    body = "".join(f"  <url><loc>{html.escape(u)}</loc></url>\n" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n'
