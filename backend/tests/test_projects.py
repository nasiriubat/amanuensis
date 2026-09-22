import os
from pathlib import Path


def test_kinds_seeded(client, admin):
    kinds = client.get("/api/kinds").json()
    slugs = [k["slug"] for k in kinds]
    assert "tool-paper" in slugs and "literature-review" in slugs and "benchmark" in slugs
    assert slugs[-1] == "other"
    k = client.get("/api/kinds/tool-paper").json()
    assert k["name"] == "Tool paper"
    assert "interview.md" in k["files"] and "Round 1" in k["files"]["interview.md"]


def test_house_style(client, admin):
    r = client.get("/api/house-style")
    assert "delve" in r.json()["content"]


def test_project_lifecycle(client, admin):
    r = client.post(
        "/api/projects", headers=admin, json={"title": "Tender Scout", "kind": "tool-paper", "venue": "LNCS"}
    )
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["slug"] == "tender-scout"
    assert p["kind_name"] == "Tool paper"
    root = Path(os.environ["DATA_DIR"]) / "projects" / "tender-scout"
    assert (root / "playbook" / "structure.md").exists()
    assert (root / ".git").exists()

    # duplicate title gets a suffix
    r2 = client.post("/api/projects", headers=admin, json={"title": "Tender Scout", "kind": "other"})
    assert r2.json()["slug"] == "tender-scout-2"

    # file edit is committed
    r = client.put("/api/projects/tender-scout/files/system-spec", headers=admin, json={"content": "# Spec\n\nHello"})
    assert r.status_code == 200
    assert client.get("/api/projects/tender-scout/files/system-spec").json()["content"].startswith("# Spec")
    hist = client.get("/api/projects/tender-scout/history?path=system-spec").json()
    assert len(hist) == 2 and "system-spec" in hist[0]["message"] and hist[1]["message"] == "Create project"
    assert client.get("/api/projects/tender-scout").json()["counts"]["has_spec"] is True

    # only allowlisted names resolve; anything else is 404 (the client normalises dot segments,
    # so traversal never even reaches the server as such)
    assert client.get("/api/projects/tender-scout/files/secret").status_code == 404
    assert client.get("/api/projects/tender-scout/files/inputs/system-spec.md").status_code == 404

    # bad kind rejected
    assert client.post("/api/projects", headers=admin, json={"title": "X", "kind": "nope"}).status_code == 400

    # delete removes tree
    assert client.delete("/api/projects/tender-scout", headers=admin).status_code == 204
    assert not root.exists()
    client.delete("/api/projects/tender-scout-2", headers=admin)


def test_profile_lifecycle(client, admin):
    r = client.post("/api/profiles", headers=admin, json={"name": "Nasir", "shareable": True})
    assert r.status_code == 201, r.text
    slug = r.json()["slug"]
    assert r.json()["status"] == "empty"
    r = client.put(f"/api/profiles/{slug}/style", headers=admin, json={"content": "Short sentences."})
    assert r.status_code == 200
    assert client.get(f"/api/profiles/{slug}").json()["status"] == "ready"

    # project can reference profile
    pid = client.get(f"/api/profiles/{slug}").json()["id"]
    r = client.post(
        "/api/projects", headers=admin, json={"title": "With profile", "kind": "tool-paper", "profile_id": pid}
    )
    assert r.json()["profile_name"] == "Nasir"
    client.delete(f"/api/projects/{r.json()['slug']}", headers=admin)
    assert client.delete(f"/api/profiles/{slug}", headers=admin).status_code == 204


def test_custom_kind(client, admin):
    r = client.post("/api/kinds", headers=admin, json={"name": "Dataset paper", "summary": "Introduces a dataset."})
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == "dataset-paper" and r.json()["builtin"] is False
    r = client.put(
        "/api/kinds/dataset-paper/files/checklist.md", headers=admin, json={"content": "# Required\n- Licence"}
    )
    assert r.status_code == 200
    assert client.put("/api/kinds/dataset-paper/files/evil.md", headers=admin, json={"content": "x"}).status_code == 400
    assert client.delete("/api/kinds/other", headers=admin).status_code == 400
    assert client.delete("/api/kinds/dataset-paper", headers=admin).status_code == 204
