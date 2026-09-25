"""Site settings, branding, SEO and editable public pages (about, contact, homepage)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import mail
from ..config import get_settings
from ..db import get_db
from ..deps import require_admin
from ..models import Page, SiteSetting, User, iso, now
from ..site_content import ABOUT_PAGE, CONTACT_PAGE, LANDING_DEFAULTS
from ..storage import slugify
from ..uploads import FILE_HEADERS, sanitize_svg, sniff

router = APIRouter(prefix="/api", tags=["site"])

DEFAULTS = {
    "name": "Coscribe",
    "tagline": "An AI co-author for people who build things and want to publish them.",
    "footer": "",
    "seo": {"title": "", "description": "", "keywords": "", "og_image": "", "index": True},
    "homepage": "landing",  # "landing", "login" or a page slug
    "logo": None,  # filename under data/branding
    "landing": LANDING_DEFAULTS,
}

_LOGO_TYPES = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}


def seed_pages(db: Session) -> None:
    """Create About and Contact once so a fresh install has something on its public site."""
    marker = db.get(SiteSetting, "pages_seeded")
    if marker or db.scalar(select(Page).limit(1)):
        return
    settings = get_settings()
    name = load_site(db)["name"]
    db.add(
        Page(
            slug="about",
            title="About",
            content=ABOUT_PAGE.format(name=name),
            published=True,
            show_in_nav=True,
            nav_order=1,
        )
    )
    db.add(
        Page(
            slug="contact",
            title="Contact",
            content=CONTACT_PAGE.format(name=name, admin_email=settings.admin_email),
            published=True,
            show_in_nav=True,
            nav_order=2,
        )
    )
    db.add(SiteSetting(key="pages_seeded", value={"at": iso(now())}))
    db.commit()


def _branding_dir() -> Path:
    d = get_settings().data_dir / "branding"
    d.mkdir(parents=True, exist_ok=True)
    return d


def study_enabled(db: Session) -> bool:
    row = db.get(SiteSetting, "study")
    return bool(row and row.value and row.value.get("enabled"))


def load_site(db: Session) -> dict:
    row = db.get(SiteSetting, "site")
    data = dict(DEFAULTS)
    if row and row.value:
        data.update(row.value)
        data["seo"] = {**DEFAULTS["seo"], **(row.value.get("seo") or {})}
        data["landing"] = {**LANDING_DEFAULTS, **(row.value.get("landing") or {})}
    return data


def save_site(db: Session, data: dict) -> dict:
    row = db.get(SiteSetting, "site")
    if not row:
        row = SiteSetting(key="site", value=data)
        db.add(row)
    else:
        row.value = data
    db.commit()
    return data


class SeoIn(BaseModel):
    title: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=400)
    keywords: str = Field(default="", max_length=400)
    og_image: str = Field(default="", max_length=500)
    index: bool = True


class PrincipleIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    text: str = Field(default="", max_length=400)


class LandingIn(BaseModel):
    eyebrow: str = Field(default="", max_length=120)
    headline: str = Field(min_length=1, max_length=120)
    subheadline: str = Field(default="", max_length=600)
    cta_primary: str = Field(default="Sign in", min_length=1, max_length=40)
    cta_secondary: str = Field(default="", max_length=40)
    why_chat: list[str] = Field(default_factory=list, max_length=8)
    why_us: list[str] = Field(default_factory=list, max_length=8)
    principles: list[PrincipleIn] = Field(default_factory=list, max_length=8)
    closing: str = Field(default="", max_length=300)


class SiteIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    tagline: str = Field(default="", max_length=200)
    footer: str = Field(default="", max_length=500)
    seo: SeoIn = Field(default_factory=SeoIn)
    homepage: str = Field(default="landing", max_length=80)
    landing: LandingIn | None = None


class PageIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=80)
    content: str = Field(default="", max_length=200_000)
    published: bool = False
    show_in_nav: bool = False
    nav_order: int = 0


class PageUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=80)
    content: str | None = Field(default=None, max_length=200_000)
    published: bool | None = None
    show_in_nav: bool | None = None
    nav_order: int | None = None


def _page_out(p: Page, full: bool = False) -> dict:
    d = {
        "id": p.id,
        "slug": p.slug,
        "title": p.title,
        "published": p.published,
        "show_in_nav": p.show_in_nav,
        "nav_order": p.nav_order,
        "updated_at": iso(p.updated_at),
    }
    if full:
        d["content"] = p.content
    return d


def _public_site(db: Session) -> dict:
    s = load_site(db)
    pages = db.scalars(
        select(Page).where(Page.published.is_(True), Page.show_in_nav.is_(True)).order_by(Page.nav_order, Page.title)
    ).all()
    return {
        "name": s["name"],
        "tagline": s["tagline"],
        "footer": s["footer"],
        "seo": s["seo"],
        "homepage": s["homepage"],
        "logo_url": f"/api/site/logo?v={re.sub(r'[^a-z0-9]', '', s['logo'] or '')}" if s.get("logo") else None,
        "nav_pages": [{"slug": p.slug, "title": p.title} for p in pages],
        "landing": s["landing"],
        "password_reset": mail.is_configured(db),
        "study_enabled": study_enabled(db),
    }


# ------------------------------------------------------------------ public


@router.get("/site")
def public_site(db: Session = Depends(get_db)):
    return _public_site(db)


@router.get("/site/logo")
def logo(db: Session = Depends(get_db)):
    s = load_site(db)
    if not s.get("logo"):
        raise HTTPException(404, "No logo")
    p = _branding_dir() / s["logo"]
    if not p.exists():
        raise HTTPException(404, "No logo")
    return FileResponse(p, headers={**FILE_HEADERS, "Cache-Control": "public, max-age=86400"})


@router.get("/pages/{slug}")
def public_page(slug: str, db: Session = Depends(get_db)):
    p = db.scalar(select(Page).where(Page.slug == slug))
    if not p or not p.published:
        raise HTTPException(404, "Page not found")
    return _page_out(p, full=True)


# ------------------------------------------------------------------ admin: site


@router.get("/admin/site")
def admin_site(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return load_site(db)


@router.put("/admin/site")
def put_site(body: SiteIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    current = load_site(db)
    if body.homepage not in ("login", "landing"):
        page = db.scalar(select(Page).where(Page.slug == body.homepage))
        if not page:
            raise HTTPException(400, "Homepage must be 'landing', 'login' or the slug of an existing page")
    incoming = body.model_dump(exclude_none=True)
    landing = {**current["landing"], **incoming.pop("landing", {})}
    data = {**current, **incoming, "landing": landing}
    return save_site(db, data)


@router.post("/admin/site/logo")
async def upload_logo(file: UploadFile = File(...), _: User = Depends(require_admin), db: Session = Depends(get_db)):
    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, "Logo larger than 2 MB")
    kind = sniff(data, _LOGO_TYPES)
    if not kind:
        raise HTTPException(400, "Use a PNG, JPEG, SVG or WebP image")
    ctype, ext = kind
    if ctype == "image/svg+xml":
        data = sanitize_svg(data)
    name = f"logo-{int(now().timestamp())}{ext}"
    d = _branding_dir()
    for old in d.glob("logo-*"):
        old.unlink()
    (d / name).write_bytes(data)
    site = load_site(db)
    site["logo"] = name
    save_site(db, site)
    return {"logo_url": f"/api/site/logo?v={name}"}


@router.delete("/admin/site/logo", status_code=204)
def delete_logo(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    for old in _branding_dir().glob("logo-*"):
        old.unlink()
    site = load_site(db)
    site["logo"] = None
    save_site(db, site)


# ------------------------------------------------------------------ admin: mail


class MailIn(BaseModel):
    enabled: bool = False
    host: str = Field(default="", max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    security: Literal["starttls", "ssl", "none"] = "starttls"
    username: str = Field(default="", max_length=255)
    password: str | None = Field(default=None, max_length=512)  # None keeps the stored one; "" clears it
    from_addr: str = Field(default="", max_length=255)
    from_name: str = Field(default="", max_length=120)


@router.get("/admin/mail")
def admin_mail(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return mail.public_view(mail.load_mail(db))


@router.put("/admin/mail")
def put_mail(body: MailIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if body.enabled and (not body.host.strip() or not body.from_addr.strip()):
        raise HTTPException(400, "Host and sender address are needed before email can be switched on")
    patch = body.model_dump(exclude={"password"})
    patch["host"] = patch["host"].strip()
    patch["from_addr"] = patch["from_addr"].strip()
    return mail.public_view(mail.update(db, patch, body.password))


@router.post("/admin/mail/test")
def test_mail(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    name = load_site(db)["name"]
    try:
        mail.send(db, admin.email, f"{name}: test message", f"Email from {name} works. Nothing else to do.\n")
    except mail.MailError as e:
        raise HTTPException(400, str(e)) from e
    return {"sent_to": admin.email}


# ------------------------------------------------------------------ admin: pages


@router.get("/admin/pages")
def list_pages(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [_page_out(p) for p in db.scalars(select(Page).order_by(Page.nav_order, Page.title)).all()]


@router.get("/admin/pages/{page_id}")
def get_page(page_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(Page, page_id)
    if not p:
        raise HTTPException(404, "Page not found")
    return _page_out(p, full=True)


def _unique_slug(db: Session, base: str, exclude_id: str | None = None) -> str:
    slug = slugify(base, max_length=60) or "page"
    if slug in ("login", "admin", "api", "assets", "p"):
        slug = f"{slug}-page"
    candidate = slug
    n = 2
    while True:
        other = db.scalar(select(Page).where(Page.slug == candidate))
        if not other or other.id == exclude_id:
            return candidate
        candidate = f"{slug}-{n}"
        n += 1


@router.post("/admin/pages", status_code=201)
def create_page(body: PageIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = Page(
        slug=_unique_slug(db, body.slug or body.title),
        title=body.title,
        content=body.content,
        published=body.published,
        show_in_nav=body.show_in_nav,
        nav_order=body.nav_order,
    )
    db.add(p)
    db.commit()
    return _page_out(p, full=True)


@router.patch("/admin/pages/{page_id}")
def update_page(page_id: str, body: PageUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(Page, page_id)
    if not p:
        raise HTTPException(404, "Page not found")
    if body.title is not None:
        p.title = body.title
    if body.slug is not None:
        p.slug = _unique_slug(db, body.slug, exclude_id=p.id)
    if body.content is not None:
        p.content = body.content
    if body.published is not None:
        p.published = body.published
    if body.show_in_nav is not None:
        p.show_in_nav = body.show_in_nav
    if body.nav_order is not None:
        p.nav_order = body.nav_order
    p.updated_at = now()
    db.commit()
    return _page_out(p, full=True)


@router.delete("/admin/pages/{page_id}", status_code=204)
def delete_page(page_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(Page, page_id)
    if not p:
        raise HTTPException(404, "Page not found")
    site = load_site(db)
    if site.get("homepage") == p.slug:
        site["homepage"] = "landing"
        save_site(db, site)
    db.delete(p)
    db.commit()


# ------------------------------------------------------------------ robots


robots_router = APIRouter(include_in_schema=False)


@robots_router.get("/robots.txt", response_class=PlainTextResponse)
def robots(db: Session = Depends(get_db)):
    s = load_site(db)
    base = get_settings().app_url.rstrip("/")
    if s["seo"].get("index", True):
        return (
            "User-agent: *\nDisallow: /api/\nDisallow: /admin\nDisallow: /projects/\nDisallow: /profiles/\n"
            f"Disallow: /library\nDisallow: /account\nDisallow: /login\nAllow: /\n\nSitemap: {base}/sitemap.xml\n"
        )
    return "User-agent: *\nDisallow: /\n"


@robots_router.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(db: Session = Depends(get_db)):
    from ..seo import sitemap

    s = load_site(db)
    if not s["seo"].get("index", True):
        raise HTTPException(404, "Not indexed")
    return PlainTextResponse(sitemap(s, db), media_type="application/xml")
