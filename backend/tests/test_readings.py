"""Background reading: ingest into readings/, card from the utility model, citable at once."""

import json

from app import storage
from app.llm.base import Completion, Usage
from app.refs import readings

CARD = {
    "question": "How do novices debug with Copilot?",
    "method": "Think-aloud study with 12 first-year students.",
    "result": "Students accepted 71% of suggestions without reading them.",
    "limitation": "One course, one semester.",
    "relation": "Same population; stops at acceptance, does not trace debugging steps.",
    "cite_for": "novices over-accept suggestions; think-aloud method for AI-assisted coding",
}


def _fake_ready_paper(folder, title="Robots Are Here", arxiv_id="2401.00001"):
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": folder.name,
        "title": title,
        "authors": ["Prather, James", "Denny, Paul"],
        "year": 2024,
        "arxiv_id": arxiv_id,
        "abstract": "We study novices and Copilot.",
        "status": "ready",
        "word_count": 5000,
        "sections": [],
    }
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (folder / "extracted.md").write_text(
        "# Robots Are Here\n\n" + "Novices accept suggestions. " * 200, encoding="utf-8"
    )
    return meta


def test_reading_card_prompt_and_summarise(client, admin, monkeypatch):
    from app.learn.context import render

    text = render("reading_card.j2", kind_name="Empirical study", title="T", spec="S", paper_title="P", paper="body")
    assert '"cite_for"' in text and "not stated" in text and "=== PAPER: P ===" in text

    async def fake_complete(db, purpose, messages, **kw):
        assert purpose == "utility" and kw.get("json_mode") is True
        return Completion(text=json.dumps(CARD), model="fake", usage=Usage(2800, 240))

    monkeypatch.setattr(readings, "complete", fake_complete)
    r = client.post("/api/projects", json={"title": "Reading Test", "kind": "empirical-study"}, headers=admin)
    slug, pid = r.json()["slug"], r.json()["id"]
    root = storage.project_dir(slug)
    _fake_ready_paper(readings.readings_dir(root) / "arxiv-2401-00001")

    import asyncio

    card = asyncio.run(readings.summarise_reading(pid, "arxiv-2401-00001"))
    assert card["ref_key"] and card["result"].startswith("Students accepted 71%")
    # the paper is now a verified reference carrying the card
    refs = client.get(f"/api/projects/{slug}/references", headers=admin).json()
    rec = next(x for x in refs if x["key"] == card["ref_key"])
    assert rec["card"]["method"].startswith("Think-aloud") and rec["reading_id"] == "arxiv-2401-00001"
    assert rec["source"] == "reading"
    # listing shows the card and key; detail returns it too
    lst = client.get(f"/api/projects/{slug}/readings", headers=admin).json()
    assert lst[0]["ref_key"] == card["ref_key"] and lst[0]["card"]["question"]
    det = client.get(f"/api/projects/{slug}/readings/arxiv-2401-00001", headers=admin).json()
    assert det["card"]["cite_for"].startswith("novices") and "Novices accept" in det["markdown"]
    # drafting context: the card replaces the abstract, expanded for related-work sections
    from app.studio import service as studio

    short = studio._ref_key_lines(root)
    full = studio._ref_key_lines(root, full_cards=True)
    assert "read in full" in short and "71%" in short and "cite for:" not in short
    assert "cite for: novices" in full and "relation to this paper:" in full
    # summarising again updates the same record instead of duplicating it
    asyncio.run(readings.summarise_reading(pid, "arxiv-2401-00001"))
    assert len(client.get(f"/api/projects/{slug}/references", headers=admin).json()) == 1
    assert client.get(f"/api/projects/{slug}", headers=admin).json()["counts"]["readings"] == 1
    # deleting the text keeps the reference
    assert client.delete(f"/api/projects/{slug}/readings/arxiv-2401-00001", headers=admin).status_code == 204
    assert len(client.get(f"/api/projects/{slug}/references", headers=admin).json()) == 1
    assert client.get(f"/api/projects/{slug}/readings", headers=admin).json() == []
    client.delete(f"/api/projects/{slug}", headers=admin)


def test_scan_adopt_as_reading_queues_ingest(client, admin, monkeypatch):
    from app.refs import scan
    from app.routers import readings as readings_router

    started = []

    def fake_start(db, user, project, *, arxiv_id=None, pdf_url=None, title=""):
        started.append(arxiv_id or pdf_url)
        return {"id": "job-x", "type": "ingest_reading", "status": "queued"}

    monkeypatch.setattr(readings_router, "start_reading_ingest", fake_start)
    r = client.post("/api/projects", json={"title": "Adopt Reading", "kind": "tool-paper"}, headers=admin)
    slug = r.json()["slug"]
    root = storage.project_dir(slug)
    scan.save_scan(
        root,
        {
            "queries": ["q"],
            "themes": ["t"],
            "candidates": [
                {
                    "title": "A",
                    "authors": ["X"],
                    "year": 2020,
                    "arxiv_id": "2001.00001",
                    "sources": ["arxiv"],
                    "relevance": 3,
                },
                {
                    "title": "B",
                    "authors": ["Y"],
                    "year": 2021,
                    "pdf_url": "https://x/y.pdf",
                    "sources": ["openalex"],
                    "relevance": 2,
                },
                {"title": "C", "authors": ["Z"], "year": 2022, "sources": ["openalex"], "relevance": 1},
            ],
            "errors": [],
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    )
    res = client.post(
        f"/api/projects/{slug}/references/scan/adopt",
        json={"idx": [0, 1, 2], "as_reference": False, "as_reading": True},
        headers=admin,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["jobs"]) == 2 and body["skipped"] == ["C"] and started == ["2001.00001", "https://x/y.pdf"]
    data = scan.load_scan(root)
    assert data["candidates"][0]["adopted_reading"] is True and not data["candidates"][2].get("adopted_reading")
    client.delete(f"/api/projects/{slug}", headers=admin)
