import subprocess
from pathlib import Path

from app.refs import bib as bib_mod
from app.refs import service as svc
from app.refs.providers import Candidate, merge

BIB = r"""
@article{smith2020tender,
  title = {Matching {SMEs} to Public Tenders},
  author = {Smith, John and Doe, Jane},
  journal = {Journal of Procurement},
  year = 2020,
  doi = {10.1000/xyz123}
}

@inproceedings{lee2019,
  title="A Tool for Something",
  author="Lee, Ann",
  booktitle="Proc. of Tools",
  year="2019",
}

@misc{noTitle, year = {2000} }
"""


def test_parse_bib_and_records():
    entries = bib_mod.parse_bib(BIB)
    assert [e["key"] for e in entries] == ["smith2020tender", "lee2019", "noTitle"]
    r = bib_mod.entry_to_record(entries[0])
    assert r["title"] == "Matching SMEs to Public Tenders"
    assert r["authors"] == ["Smith, John", "Doe, Jane"]
    assert r["year"] == 2020 and r["doi"] == "10.1000/xyz123" and r["venue"] == "Journal of Procurement"
    r2 = bib_mod.entry_to_record(entries[1])
    assert r2["venue"] == "Proc. of Tools" and r2["year"] == 2019


def test_key_generation_and_bibtex_roundtrip():
    taken = {"smith2020matching"}
    k = bib_mod.make_key(["John Smith", "Jane Doe"], 2020, "Matching SMEs to Public Tenders", taken)
    assert k == "smith2020matchinga"
    assert bib_mod.make_key(["Doe, Jane"], None, "The of a Tool", set()) == "doetool"
    rec = {
        "key": "x2021y",
        "title": "T & U",
        "authors": ["A B"],
        "year": 2021,
        "venue": "V",
        "bibtype": "inproceedings",
        "doi": "10.1/2",
    }
    tex = bib_mod.record_to_bibtex(rec)
    assert tex.startswith("@inproceedings{x2021y,") and "booktitle = {V}" in tex and "\\&" in tex
    parsed = bib_mod.parse_bib(tex)
    assert parsed[0]["fields"]["doi"] == "10.1/2"


def test_merge_dedupes_by_doi_and_title():
    a = Candidate(
        title="Deep Tender Matching",
        authors=["A"],
        year=2020,
        doi="10.1/A",
        source="semanticscholar",
        score=1.0,
        citation_count=10,
    )
    b = Candidate(title="Deep tender matching.", authors=["A"], year=2020, doi=None, source="openalex", score=0.5)
    c = Candidate(title="Other", authors=["B"], year=2019, doi="10.1/B", source="arxiv", score=0.8)
    merged = merge([[a], [b], [c]])
    assert len(merged) == 2
    top = merged[0]
    assert top.title == "Deep Tender Matching" and set(top.sources) == {"semanticscholar", "openalex"}
    assert top.citation_count == 10


def test_records_store_and_requests(tmp_path: Path):
    root = tmp_path / "proj"
    (root / "references").mkdir(parents=True)
    (root / "sections").mkdir()
    subprocess.run(["git", "init", "-q", root], check=True)
    r = svc.accept(
        root,
        {
            "title": "Deep Tender Matching",
            "authors": ["Ada Lovelace"],
            "year": 2020,
            "source": "openalex",
            "doi": "10.1/A",
        },
    )
    assert r["key"] == "lovelace2020deep" and r["verified_at"]
    assert svc.keys(root) == {"lovelace2020deep"}
    bib = (root / "references" / "refs.bib").read_text()
    assert "@misc{lovelace2020deep," in bib and "doi = {10.1/A}" in bib

    res = svc.import_bib(root, BIB)
    assert res["added"] == ["smith2020tender", "lee2019"] and res["skipped"] == ["noTitle"]
    assert len(svc.list_records(root)) == 3
    assert "@article{smith2020tender," in (root / "references" / "refs.bib").read_text()

    # duplicate key on import gets a generated key
    res2 = svc.import_bib(root, "@article{lee2019, title={Another}, author={Kim, Bo}, year={2019}}")
    assert res2["added"] == ["kim2019another"]

    # citation requests from placeholders and usage counts
    (root / "sections" / "index.json").write_text(
        '{"sections": [{"id": "s1", "title": "Related Work", "file": "01.md"}]}'
    )
    (root / "sections" / "01.md").write_text(
        "Prior work [@lee2019] and [@lee2019; @missing]. [CITE: evidence that CPV filters miss tenders]"
    )
    reqs = svc.requests(root)
    assert reqs == [
        {
            "section": "Related Work",
            "section_id": "s1",
            "text": "evidence that CPV filters miss tenders",
            "query": "CPV filters miss tenders",
        }
    ]
    assert svc.usage(root) == {"lee2019": 2, "missing": 1}

    assert svc.delete(root, "lee2019") is True
    assert svc.delete(root, "../x") is False
    assert "lee2019" not in svc.keys(root)


def test_references_api(client, admin):
    r = client.post("/api/projects", headers=admin, json={"title": "Refs flow", "kind": "tool-paper"})
    slug = r.json()["slug"]
    assert client.get(f"/api/projects/{slug}/references").json() == []
    r = client.post(
        f"/api/projects/{slug}/references/manual",
        headers=admin,
        json={"title": "Manual One", "authors": ["Z Zed"], "year": 2022},
    )
    assert r.status_code == 201 and r.json()["key"] == "zed2022manual" and r.json()["source"] == "manual"
    assert "zed2022manual" in client.get(f"/api/projects/{slug}/references/bib").text
    assert client.get(f"/api/projects/{slug}").json()["counts"]["references"] == 1
    assert client.delete(f"/api/projects/{slug}/references/zed2022manual", headers=admin).status_code == 204
    assert client.delete(f"/api/projects/{slug}/references/zed2022manual", headers=admin).status_code == 404
    client.delete(f"/api/projects/{slug}", headers=admin)
