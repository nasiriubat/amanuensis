from pathlib import Path

from app.studio import lint as lint_mod
from app.studio import service as svc

HOUSE = """# House style

## Banned words and phrases

Never use these. They are the fingerprints of machine text.

delve, delve into, tapestry, landscape (figurative), leverage (as a verb), it is worth noting,
not only ... but also, plays a crucial role.

## Patterns to avoid
- Triads.
"""

OUTLINE = """# Outline: T

## 1. Abstract (≈ 80 words)
- Summarise the tool.

## Introduction (≈ 900 words)
- Open with the pain.
- [NEEDS: a concrete scenario]
- State contributions.

## Evaluation / Demonstration (≈ 350 words)
- Method.
- [NEEDS: results of the pilot]

## Open items
- [NEEDS: a concrete scenario] (Introduction)
"""


def test_banned_phrase_parsing():
    phrases = lint_mod.banned_phrases(HOUSE)
    assert "delve" in phrases and "leverage" in phrases and "it is worth noting" in phrases
    assert "landscape" in phrases  # parenthetical qualifier stripped
    assert not any(p.startswith("never") for p in phrases)


def test_lint_findings():
    long = (
        "Furthermore, this is a sentence that keeps going and going with clause after clause after clause "
        "because nobody stopped it and it now has far more than thirty five words in total which is too many."
    )
    text = (
        "# Heading\n\n"
        "We delve into the problem — it is worth noting that tools matter; users agree!\n\n"
        f"{long}\n\n"
        "Furthermore, prior work [@smith2020] and [@ok2021; @nope] found things. "
        "[NEEDS: numbers] Is this good?\n"
    )
    f = lint_mod.lint(text, HOUSE, known_keys={"ok2021"})
    kinds = {x["kind"] for x in f}
    assert {"banned", "dash", "semicolon", "exclamation", "long", "opener", "citation", "needs", "question"} <= kinds
    cites = [x for x in f if x["kind"] == "citation" and x["severity"] == "error"]
    assert {c["excerpt"] for c in cites} == {"[@smith2020]", "[@ok2021; @nope]"}
    assert all(x["line"] >= 1 for x in f)
    summary = lint_mod.summarize(f)
    assert summary["errors"] == 2 and summary["warnings"] >= 4


def test_outline_parsing_and_init(tmp_path: Path):
    parsed = svc.parse_outline(OUTLINE)
    assert [p["title"] for p in parsed] == ["Abstract", "Introduction", "Evaluation / Demonstration"]
    assert parsed[1]["target_words"] == 900 and len(parsed[1]["lines"]) == 3

    root = tmp_path / "proj"
    (root / "inputs").mkdir(parents=True)
    (root / "outline.md").write_text(OUTLINE)
    (root / "references").mkdir()
    (root / "references" / "refs.bib").write_text("@article{ok2021, title={x}}\n")
    import subprocess

    subprocess.run(["git", "init", "-q", root], check=True)
    index = svc.init_sections(root)
    files = sorted(p.name for p in (root / "sections").iterdir())
    assert files == ["01-abstract.md", "02-introduction.md", "03-evaluation-demonstration.md", "index.json"]
    assert index["sections"][1]["target_words"] == 900

    items = svc.load_checklist(root)
    assert {i["text"] for i in items} == {"a concrete scenario", "results of the pilot"}
    assert all(i["source"] == "outline" for i in items)

    # re-init keeps sections and does not duplicate checklist items
    sec = index["sections"][1]
    svc.save_section_text(root, sec, "We open with the pain. [NEEDS: a number]", by_user=True)
    index2 = svc.init_sections(root)
    assert index2["sections"][1]["id"] == sec["id"] and index2["sections"][1]["status"] == "edited"
    texts = [i["text"] for i in svc.load_checklist(root)]
    assert texts.count("a concrete scenario") == 1 and "a number" in texts

    # placeholder removed from the draft closes the draft-sourced item
    svc.save_section_text(root, index2["sections"][1], "We open with the pain. Now with 12 users.", by_user=True)
    by_text = {i["text"]: i for i in svc.load_checklist(root)}
    assert by_text["a number"]["status"] == "resolved"
    assert by_text["a concrete scenario"]["status"] == "open"  # outline-sourced items stay until the user resolves them

    assert svc.known_ref_keys(root) == {"ok2021"}
    hist = svc.history(root, index2["sections"][1])
    assert len(hist) >= 2
    assert "12 users" in svc.version_text(root, index2["sections"][1], hist[0]["sha"])
    assert "[NEEDS: a number]" in svc.version_text(root, index2["sections"][1], hist[1]["sha"])


def test_section_bucket_matching():
    assert svc._bucket("Tool Overview / Architecture") == "design"
    assert svc._bucket("Related Work") == "related"
    assert svc._bucket("Evaluation / Demonstration") == "evaluation"
    assert svc._bucket("Data Availability") is None


def test_studio_api_requires_approved_outline(client, admin):
    r = client.post("/api/projects", headers=admin, json={"title": "Studio flow", "kind": "tool-paper"})
    slug = r.json()["slug"]
    assert client.get(f"/api/projects/{slug}/studio").json()["initialized"] is False
    assert client.post(f"/api/projects/{slug}/studio/init", headers=admin).status_code == 400
    f = client.post(f"/api/projects/{slug}/lint", headers=admin, json={"text": "We delve — deeply."}).json()
    assert {x["kind"] for x in f} >= {"banned", "dash"}
    client.delete(f"/api/projects/{slug}", headers=admin)
