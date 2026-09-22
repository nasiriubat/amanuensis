"""Render every prompt template with representative data so Jinja errors surface in CI, not in a paid LLM call."""

from app.learn.context import render


def test_paper_summary_renders():
    out = render(
        "paper_summary.j2",
        kind_name="Tool paper",
        paper="## Introduction\n\nText.",
        sections=[{"level": 2, "title": "Introduction", "words": 350}, {"level": 3, "title": "Sub", "words": 80}],
        total_words=4200,
    )
    assert "Tool paper" in out
    assert "## Introduction — 350 words" in out and "### Sub — 80 words" in out
    assert "4200 words" in out
    assert "=== PAPER" in out


def test_playbook_renders_with_and_without_kind_notes():
    base = dict(kind_name="Tool paper", summaries=['{"title": "A"}', '{"title": "B"}'])
    with_notes = render("playbook.j2", kind_notes="# Tool paper\n\nNotes.", **base)
    without = render("playbook.j2", kind_notes="", **base)
    assert "Notes." in with_notes and "Notes." not in without
    assert "--- Paper 2 ---" in without
    for key in ("structure", "argumentation", "evaluation", "related_work", "venue"):
        assert f'"{key}"' in without


def test_style_templates_render():
    s = render("style_sample.j2", sample="We built it. It works.")
    assert "We built it." in s
    p = render("style_profile.j2", profile_name="Nasir", stats='{"papers": 2}', observations=['{"openers": []}'])
    assert "# Voice: Nasir" in p and "--- Paper 1 ---" in p


def test_draft_system_forbids_invented_example_particulars():
    from app.learn.context import render

    out = render(
        "draft_system.j2", kind_name="Tool paper", profile="", house_style="", playbook="", facts="", ref_keys=""
    )
    assert "illustrative material" in out and "Never state a particular and then ask for it" in out
