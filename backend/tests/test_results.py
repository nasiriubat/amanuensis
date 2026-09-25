"""Results tables: CSV and XLSX upload, summaries, snippet, and their place in prompts."""

import io

from openpyxl import Workbook

from app import storage
from app.figures import tables


def test_csv_and_xlsx_tables_round_trip(client, admin):
    r = client.post("/api/projects", json={"title": "Results", "kind": "empirical-study"}, headers=admin)
    slug = r.json()["slug"]
    csv_bytes = b"condition;seconds;passed\nbaseline;12.5;yes\nwith tool;8.1;yes\nwith tool;9.4;no\n"
    up = client.post(
        f"/api/projects/{slug}/results/upload",
        files={"file": ("Run Times.csv", csv_bytes, "text/csv")},
        data={"caption": "Time to first fix per condition"},
        headers=admin,
    )
    assert up.status_code == 201, up.text
    t = up.json()
    assert t["name"] == "run-times" and t["columns"] == ["condition", "seconds", "passed"] and t["rows"] == 3
    seconds = next(s for s in t["summary"] if s["column"] == "seconds")
    assert seconds["kind"] == "number" and seconds["min"] == 8.1 and seconds["max"] == 12.5
    cond = next(s for s in t["summary"] if s["column"] == "condition")
    assert cond["kind"] == "text" and cond["distinct"] == 2

    wb = Workbook()
    ws = wb.active
    ws.append(["participant", "sus"])
    ws.append(["P1", 72.5])
    ws.append(["P2", 80])
    buf = io.BytesIO()
    wb.save(buf)
    up2 = client.post(
        f"/api/projects/{slug}/results/upload",
        files={"file": ("sus scores.xlsx", buf.getvalue(), "application/octet-stream")},
        headers=admin,
    )
    assert up2.status_code == 201, up2.text
    assert up2.json()["name"] == "sus-scores" and up2.json()["rows"] == 2

    lst = client.get(f"/api/projects/{slug}/results", headers=admin).json()
    assert [x["name"] for x in lst] == ["run-times", "sus-scores"]
    prev = client.get(f"/api/projects/{slug}/results/run-times/preview", headers=admin).json()
    assert prev["total"] == 3 and prev["rows"][1] == ["with tool", "8.1", "yes"]
    snip = client.get(f"/api/projects/{slug}/results/run-times/snippet", headers=admin).json()["markdown"]
    assert (
        "| condition | seconds | passed |" in snip and "Table: Time to first fix per condition {#tbl:run-times}" in snip
    )

    root = storage.project_dir(slug)
    block = tables.prompt_block(root)
    assert "Table run-times" in block and "seconds: numbers, n=3, min 8.1, max 12.5" in block and "sus-scores" in block
    # facts and drafting prompts carry the tables
    from app.learn.context import render

    facts = render("facts.j2", spec="S", plan="", interview="", results=block)
    assert "RESULTS TABLES" in facts and "table <name>" in facts
    draft = render(
        "draft_section.j2",
        title="T",
        section={"title": "Evaluation", "order": 1, "lines": ["Report results."], "target_words": 300},
        total=1,
        outline_compact="",
        instructions="",
        current="",
        spec="S",
        interview="",
        plan="",
        previous="",
        others="",
        exemplars="",
        results=block,
    )
    assert "RESULTS TABLES" in draft and "quote numbers exactly" in draft

    bad = client.post(
        f"/api/projects/{slug}/results/upload",
        files={"file": ("notes.docx", b"PK\x03\x04junk", "application/octet-stream")},
        headers=admin,
    )
    assert bad.status_code == 400
    assert (
        client.patch(f"/api/projects/{slug}/results/run-times", json={"caption": "New"}, headers=admin).json()[
            "caption"
        ]
        == "New"
    )
    assert client.delete(f"/api/projects/{slug}/results/run-times", headers=admin).status_code == 204
    assert client.delete(f"/api/projects/{slug}/results/run-times", headers=admin).status_code == 404
    client.delete(f"/api/projects/{slug}", headers=admin)


def test_card_budget_expands_only_the_closest_cards(tmp_path, monkeypatch):
    from app.studio import service as studio

    records = []
    for i in range(20):
        topic = "debugging novices" if i < 3 else f"topic{i} unrelated matter"
        records.append(
            {
                "key": f"k{i:02d}",
                "title": f"Paper {i} on {topic}",
                "authors": ["A"],
                "year": 2020,
                "card": {
                    "question": topic,
                    "method": "m",
                    "result": "r",
                    "limitation": "not stated",
                    "relation": "",
                    "cite_for": topic,
                },
            }
        )
    from app.refs import service as refs

    monkeypatch.setattr(refs, "list_records", lambda root: records)
    out = studio._ref_key_lines(tmp_path, full_cards=True, focus="How novices debug with assistants")
    assert out.count("cite for:") == studio.CARD_FULL_LIMIT
    assert "[@k00]" in out and out.index("cite for: debugging novices") < out.index("[@k03]")
    short = studio._ref_key_lines(tmp_path, full_cards=False)
    assert "cite for:" not in short


def test_stemming_matches_inflections():
    from app.refs.evidence import _tokens

    assert set(_tokens("Students accepted the suggestions")) == set(_tokens("student accepts a suggestion"))
