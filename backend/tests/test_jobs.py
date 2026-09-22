import time

from app.ingest import service as ingest_service


def _wait(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "failed"):
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_ingest_job_runs_on_event_loop(client, admin, monkeypatch):
    """Starting a job from a request must schedule it on the server loop and report progress."""

    async def fake_ingest(root, arxiv_id, ctx):
        ctx.progress(50, "halfway")
        return {"id": f"arxiv-{arxiv_id}", "title": "Fake", "word_count": 1, "source": "test"}

    monkeypatch.setattr(ingest_service, "ingest_arxiv", fake_ingest)
    r = client.post("/api/projects", headers=admin, json={"title": "Jobs test", "kind": "tool-paper"})
    slug = r.json()["slug"]
    r = client.post(f"/api/projects/{slug}/exemplars/arxiv", headers=admin, json={"ref": "2405.15793"})
    assert r.status_code == 202, r.text
    job = _wait(client, r.json()["id"])
    assert job["status"] == "done"
    assert job["result"]["title"] == "Fake"
    assert job["progress"] == 100

    # failures are captured, never crash the server
    async def boom(root, arxiv_id, ctx):
        raise ValueError("nope")

    monkeypatch.setattr(ingest_service, "ingest_arxiv", boom)
    r = client.post(f"/api/projects/{slug}/exemplars/arxiv", headers=admin, json={"ref": "2405.15793"})
    job = _wait(client, r.json()["id"])
    assert job["status"] == "failed" and "nope" in job["error"]

    assert (
        client.post(f"/api/projects/{slug}/exemplars/arxiv", headers=admin, json={"ref": "garbage"}).status_code == 400
    )
    client.delete(f"/api/projects/{slug}", headers=admin)


def test_learn_requires_exemplars(client, admin):
    r = client.post("/api/projects", headers=admin, json={"title": "Learn test", "kind": "tool-paper"})
    slug = r.json()["slug"]
    r = client.post(f"/api/projects/{slug}/learn", headers=admin, json={"max_chars_per_paper": 15000})
    assert r.status_code == 202
    job = _wait(client, r.json()["id"])
    assert job["status"] == "failed" and "No ingested exemplars" in job["error"]
    client.delete(f"/api/projects/{slug}", headers=admin)
