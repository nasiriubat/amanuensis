"""Landing settings, seeded pages, SEO head, upload sniffing and admin cleanup."""

from __future__ import annotations

import io

from conftest import login

from app.seo import head_for, inject
from app.uploads import sanitize_svg, sniff


def test_landing_defaults_and_seeded_pages(client):
    r = client.get("/api/site")
    assert r.status_code == 200
    s = r.json()
    assert s["homepage"] == "landing"
    assert s["landing"]["headline"]
    assert len(s["landing"]["principles"]) >= 3
    slugs = {p["slug"] for p in s["nav_pages"]}
    assert {"about", "contact"} <= slugs
    about = client.get("/api/pages/about").json()
    assert "Paper Writer" in about["content"]
    contact = client.get("/api/pages/contact").json()
    assert "admin@test.local" in contact["content"]


def test_admin_edits_landing_and_homepage_validation(client, admin):
    site = client.get("/api/admin/site", headers=admin).json()
    body = {
        **site,
        "landing": {**site["landing"], "headline": "Publish what you built", "why_us": ["Files, not chat."]},
    }
    body.pop("logo", None)
    r = client.put("/api/admin/site", json=body, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["landing"]["headline"] == "Publish what you built"
    assert r.json()["landing"]["why_us"] == ["Files, not chat."]
    # untouched landing fields survive a partial update
    assert r.json()["landing"]["principles"]
    public = client.get("/api/site").json()
    assert public["landing"]["headline"] == "Publish what you built"
    bad = client.put("/api/admin/site", json={**body, "homepage": "no-such-page"}, headers=admin)
    assert bad.status_code == 400


def test_robots_sitemap_and_security_headers(client):
    r = client.get("/robots.txt")
    assert "Sitemap:" in r.text and "Disallow: /api/" in r.text
    sm = client.get("/sitemap.xml")
    assert sm.status_code == 200
    assert "/p/about" in sm.text and "<urlset" in sm.text
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["cache-control"] == "no-store"


def test_oversized_request_rejected_early(client, admin):
    r = client.post(
        "/api/admin/site/logo",
        headers={**admin, "content-length": str(50 * 1024 * 1024)},
        files={"file": ("big.png", b"x", "image/png")},
    )
    assert r.status_code == 413


def test_seo_head_for_public_and_private_routes(client):
    from app.db import SessionLocal
    from app.routers.site import load_site

    with SessionLocal() as db:
        s = load_site(db)
        home = head_for("", s, db)
        assert home["robots"] == "index, follow"
        assert home["ld"]["@type"] == "SoftwareApplication"
        about = head_for("p/about", s, db)
        assert about["title"].startswith("About ·")
        assert about["description"]
        assert about["ld"]["@type"] == "WebPage"
        priv = head_for("projects/x/studio", s, db)
        assert priv["robots"] == "noindex, nofollow"
        assert priv["canonical"] == ""
        missing = head_for("p/nope", s, db)
        assert missing["robots"] == "noindex, nofollow"
    html = inject("<html><head><title>x</title></head><body></body></html>", about)
    assert "<title>About ·" in html and 'rel="canonical"' in html and "ld+json" in html
    assert html.count("<title>") == 1


def test_sniff_and_svg_sanitizer():
    assert sniff(b"\x89PNG\r\n\x1a\n" + b"0" * 16, {"image/png"}) == ("image/png", ".png")
    assert sniff(b"%PDF-1.7 ...", {"application/pdf", "image/png"}) == ("application/pdf", ".pdf")
    assert sniff(b"GIF89a....", {"image/png", "image/jpeg"}) is None
    assert sniff(b"<html><svg></svg></html>", {"image/svg+xml"}) is None
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><script>alert(2)</script>'
        b'<a href="javascript:alert(3)"><rect onclick="x()" width="1"/></a>'
        b"<foreignObject><body>hi</body></foreignObject></svg>"
    )
    clean = sanitize_svg(svg)
    assert b"<script" not in clean and b"onload" not in clean and b"onclick" not in clean
    assert b"javascript:" not in clean and b"foreignObject" not in clean
    assert b"<rect" in clean


def test_logo_upload_checks_bytes_not_content_type(client, admin):
    fake = client.post(
        "/api/admin/site/logo", headers=admin, files={"file": ("logo.png", b"not an image", "image/png")}
    )
    assert fake.status_code == 400
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><script>alert(1)</script><circle r="4"/></svg>'
    )
    ok = client.post(
        "/api/admin/site/logo", headers=admin, files={"file": ("logo.svg", svg, "application/octet-stream")}
    )
    assert ok.status_code == 200, ok.text
    served = client.get("/api/site/logo")
    assert served.status_code == 200
    assert b"<script" not in served.content
    assert "sandbox" in served.headers["content-security-policy"]
    client.delete("/api/admin/site/logo", headers=admin)


def test_bib_import_requires_bib_text(client, admin):
    r = client.post("/api/projects", json={"title": "Bib Guard", "kind": "tool-paper"}, headers=admin)
    slug = r.json()["slug"]
    bad = client.post(
        f"/api/projects/{slug}/references/import-bib",
        headers=admin,
        files={"file": ("refs.pdf", b"%PDF-", "application/pdf")},
    )
    assert bad.status_code == 400
    binary = client.post(
        f"/api/projects/{slug}/references/import-bib",
        headers=admin,
        files={"file": ("refs.bib", b"\x00\x01\x02", "text/plain")},
    )
    assert binary.status_code == 400
    good = client.post(
        f"/api/projects/{slug}/references/import-bib",
        headers=admin,
        files={
            "file": (
                "refs.bib",
                io.BytesIO(b"@article{k1, title={A paper}, author={A. B.}, year={2020}}").getvalue(),
                "text/plain",
            )
        },
    )
    assert good.status_code == 200, good.text
    assert good.json()["added"] == ["k1"]
    client.delete(f"/api/projects/{slug}", headers=admin)


def test_figure_upload_sniffs_and_serves_sandboxed(client, admin):
    r = client.post("/api/projects", json={"title": "Fig Guard", "kind": "tool-paper"}, headers=admin)
    slug = r.json()["slug"]
    bad = client.post(
        f"/api/projects/{slug}/figures/upload",
        headers=admin,
        data={"name": "plot", "caption": ""},
        files={"file": ("plot.png", b"<html>nope</html>", "image/png")},
    )
    assert bad.status_code == 400
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>x()</script><rect width="2" height="2"/></svg>'
    ok = client.post(
        f"/api/projects/{slug}/figures/upload",
        headers=admin,
        data={"name": "plot", "caption": "A plot"},
        files={"file": ("plot.svg", svg, "text/plain")},
    )
    assert ok.status_code == 201, ok.text
    served = client.get(f"/api/projects/{slug}/figures/plot/file")
    assert served.status_code == 200
    assert b"<script" not in served.content
    assert "sandbox" in served.headers["content-security-policy"]
    client.delete(f"/api/projects/{slug}", headers=admin)


def test_storage_overview_and_cleanup(client, admin):
    from datetime import timedelta

    from app.db import SessionLocal
    from app.models import AuthSession, Job, LlmCall, User, now

    r = client.post("/api/projects", json={"title": "Storage Demo", "kind": "tool-paper"}, headers=admin)
    slug = r.json()["slug"]
    pid = r.json()["id"]
    with SessionLocal() as db:
        uid = db.scalar(__import__("sqlalchemy").select(User.id).limit(1))
        old = now() - timedelta(days=400)
        db.add(Job(user_id=uid, project_id=pid, type="export", status="done", created_at=old, updated_at=old))
        db.add(Job(user_id=uid, project_id=pid, type="export", status="running"))
        db.add(
            LlmCall(
                user_id=uid,
                project_id=pid,
                purpose="draft",
                provider_name="p",
                model="m",
                input_tokens=1,
                output_tokens=1,
                created_at=old,
            )
        )
        db.add(AuthSession(id="deadbeef" * 8, user_id=uid, csrf_token="c" * 32, expires_at=old, created_at=old))
        db.commit()
    from app import storage

    ex = storage.project_dir(slug) / "exports"
    for stamp in ("20260101-000000", "20260102-000000", "20260103-000000", "20260104-000000"):
        (ex / stamp).mkdir(parents=True)
        (ex / stamp / "paper.pdf").write_bytes(b"%PDF-" + b"0" * 1000)

    ov = client.get("/api/admin/storage", headers=admin).json()
    assert ov["total"] > 0
    proj = next(p for p in ov["projects"] if p["slug"] == slug)
    assert proj["exports_count"] == 4 and proj["exports"] >= 4000
    assert ov["counts"]["sessions_expired"] >= 1 and ov["counts"]["jobs_finished"] >= 1

    res = client.post(
        "/api/admin/storage/cleanup",
        json={
            "actions": ["exports", "jobs", "llm_calls", "sessions", "vacuum", "history"],
            "keep_exports": 2,
            "older_than_days": 90,
        },
        headers=admin,
    )
    assert res.status_code == 200, res.text
    rep = res.json()["report"]
    assert rep["exports"]["removed"] == 2 and rep["exports"]["freed"] >= 2000
    assert rep["jobs"]["removed"] >= 1 and rep["llm_calls"]["removed"] >= 1 and rep["sessions"]["removed"] >= 1
    assert sorted(x.name for x in ex.iterdir()) == ["20260103-000000", "20260104-000000"]
    with SessionLocal() as db:
        assert (
            db.scalar(__import__("sqlalchemy").select(Job).where(Job.status == "running", Job.project_id == pid))
            is not None
        )
    bad = client.post("/api/admin/storage/cleanup", json={"actions": ["drop-tables"]}, headers=admin)
    assert bad.status_code == 400
    # members cannot reach it
    client.post(
        "/api/users",
        json={"email": "m@test.local", "display_name": "M", "password": "memberpass1", "role": "user"},
        headers=admin,
    )
    member = login(client, "m@test.local", "memberpass1")
    assert client.get("/api/admin/storage", headers=member).status_code == 403
    login(client)
    client.delete(f"/api/projects/{slug}", headers=admin)


def test_backup_zip_contains_db_and_files(client, admin):
    import io
    import zipfile

    r = client.post("/api/projects", json={"title": "Backup Demo", "kind": "tool-paper"}, headers=admin)
    slug = r.json()["slug"]
    from app import storage

    (storage.project_dir(slug) / "exports" / "20260101-000000").mkdir(parents=True)
    (storage.project_dir(slug) / "exports" / "20260101-000000" / "paper.pdf").write_bytes(b"%PDF-")
    res = client.get("/api/admin/storage/backup?include_exports=false", headers=admin)
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(res.content)).namelist()
    assert "app.db" in names and "RESTORE.txt" in names
    assert any(n.startswith(f"projects/{slug}/") for n in names)
    assert not any("/exports/" in n for n in names)
    assert not any("/.git/" in n for n in names)
    with_exports = client.get("/api/admin/storage/backup?include_exports=true", headers=admin)
    assert any("/exports/" in n for n in zipfile.ZipFile(io.BytesIO(with_exports.content)).namelist())
    client.delete(f"/api/projects/{slug}", headers=admin)
