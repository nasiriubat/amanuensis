"""User study kit: opt-in events, summary, CSV, documents, guide page."""

from conftest import login


def test_events_are_ignored_until_enabled_then_recorded_and_summarised(client, admin):
    r = client.post("/api/projects", json={"title": "Study Paper", "kind": "tool-paper"}, headers=admin)
    slug = r.json()["slug"]
    assert client.get("/api/site").json()["study_enabled"] is False
    ev = {"kind": "page", "project_slug": slug, "path": f"/projects/{slug}/spec"}
    assert client.post("/api/events", json=ev, headers=admin).status_code == 204
    st = client.get("/api/admin/study", headers=admin).json()
    assert st["enabled"] is False and st["events"] == 0

    assert client.put("/api/admin/study", json={"enabled": True}, headers=admin).json()["enabled"] is True
    assert client.get("/api/site").json()["study_enabled"] is True
    client.post("/api/events", json=ev, headers=admin)
    client.post("/api/events", json={**ev, "path": f"/projects/{slug}/studio"}, headers=admin)
    long_text = {"kind": "section_saved", "project_slug": slug, "meta": {"words": 120, "text": "x" * 500, "ok": True}}
    client.post("/api/events", json=long_text, headers=admin)
    client.post("/api/events", json={"kind": "not-a-kind", "project_slug": slug}, headers=admin)
    st = client.get("/api/admin/study", headers=admin).json()
    assert st["events"] == 3
    row = next(p for p in st["projects"] if p["slug"] == slug)
    assert row["events"] == 3 and row["event_kinds"] == {"page": 2, "section_saved": 1}
    assert row["owner"] == "Admin" and "tokens_total" in row and row["exports"] == 0
    csv_text = client.get("/api/admin/study/events.csv", headers=admin).text
    assert "admin@test.local" in csv_text and slug in csv_text and "spec" in csv_text
    assert "x" * 100 not in csv_text and "text" not in csv_text.split("\n")[-2]  # long strings dropped
    assert '""words"": 120' in csv_text  # numbers kept (CSV doubles the JSON quotes)
    js = client.get("/api/admin/study/summary.json", headers=admin)
    assert js.headers["content-type"].startswith("application/json") and slug in js.text

    kit = client.get("/api/admin/study/kit", headers=admin).json()
    assert [k["name"] for k in kit] == ["participant-guide.md", "consent.md", "questionnaire.md", "interview-guide.md"]
    assert kit[2]["title"] == "End-of-study questionnaire" and "System Usability Scale" in kit[2]["content"]
    g = client.post("/api/admin/study/guide-page", headers=admin)
    assert g.status_code == 201 and g.json()["created"] is True
    again = client.post("/api/admin/study/guide-page", headers=admin).json()
    assert again["created"] is False and again["slug"] == g.json()["slug"]
    pages = client.get("/api/admin/pages", headers=admin).json()
    guide = next(p for p in pages if p["slug"] == g.json()["slug"])
    assert guide["published"] is False

    # members can post events but not read the study
    client.post(
        "/api/users",
        json={"email": "sam@test.local", "display_name": "Sam", "password": "sam-pass-1234"},
        headers=admin,
    )
    sam = login(client, "sam@test.local", "sam-pass-1234")
    assert client.post("/api/events", json={"kind": "page", "path": "/library"}, headers=sam).status_code == 204
    assert client.get("/api/admin/study", headers=sam).status_code == 403
    admin = login(client)
    assert client.delete("/api/admin/study/events", headers=admin).status_code == 204
    assert client.get("/api/admin/study", headers=admin).json()["events"] == 0
    client.put("/api/admin/study", json={"enabled": False}, headers=admin)
    for u in client.get("/api/users", headers=admin).json():
        if u["email"] == "sam@test.local":
            client.delete(f"/api/users/{u['id']}", headers=admin)
    client.delete(f"/api/projects/{slug}", headers=admin)
