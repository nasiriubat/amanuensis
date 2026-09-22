import json
from pathlib import Path

from app.interview import service as svc
from app.learn.context import render


def _state_with_round(root: Path):
    state = {
        "rounds": [
            {
                "index": 1,
                "title": "Users and problem",
                "rationale": "start",
                "questions": [
                    {
                        "id": "a",
                        "question": "Who uses it?",
                        "why": "intro",
                        "suggested": "SMEs",
                        "confidence": "high",
                        "answer": "",
                        "status": "open",
                    },
                    {
                        "id": "b",
                        "question": "How many?",
                        "why": "eval",
                        "suggested": "",
                        "confidence": "low",
                        "answer": "",
                        "status": "open",
                    },
                ],
            }
        ],
        "notes": [],
    }
    (root / "inputs").mkdir(parents=True, exist_ok=True)
    (root / "inputs" / "interview.json").write_text(json.dumps(state))
    return state


def test_answers_render_and_persist(tmp_path):
    root = tmp_path / "proj"
    _state_with_round(root)
    svc.apply_answers(root, [{"id": "a", "answer": "Bid managers in Finnish SMEs."}, {"id": "b", "status": "na"}])
    state = svc.load_interview(root)
    qs = {q["id"]: q for q in state["rounds"][0]["questions"]}
    assert qs["a"]["status"] == "answered" and qs["b"]["status"] == "na"
    md = (root / "inputs" / "interview.md").read_text()
    assert "## Round 1: Users and problem" in md
    assert "**A:** Bid managers in Finnish SMEs." in md
    assert "Not applicable." in md
    # unknown ids are ignored, nothing crashes
    svc.apply_answers(root, [{"id": "zzz", "answer": "x"}])
    svc.pin_note(root, "The matcher uses embeddings.")
    md = (root / "inputs" / "interview.md").read_text()
    assert "Notes pinned from chat" in md and "embeddings" in md


def test_interview_api_flow(client, admin):
    r = client.post("/api/projects", headers=admin, json={"title": "Interview flow", "kind": "tool-paper"})
    slug = r.json()["slug"]
    assert client.get(f"/api/projects/{slug}/interview").json() == {"rounds": [], "notes": [], "updated_at": None}
    # design needs an idea first
    assert (
        client.post(f"/api/projects/{slug}/design/generate", headers=admin, json={"mode": "refine"}).status_code == 400
    )
    # outline needs a spec first
    assert client.post(f"/api/projects/{slug}/outline/generate", headers=admin).status_code == 400
    assert client.post(f"/api/projects/{slug}/outline/approve", headers=admin).status_code == 400
    # idea and plan are editable files
    assert client.put(f"/api/projects/{slug}/files/idea", headers=admin, json={"content": "An idea"}).status_code == 200
    assert client.get(f"/api/projects/{slug}/files/research-plan").json()["content"] == ""
    counts = client.get(f"/api/projects/{slug}").json()["counts"]
    assert counts["interview_rounds"]["rounds"] == 0 and counts["has_plan"] is False
    assert client.get(f"/api/projects/{slug}/chat").json() == []
    client.delete(f"/api/projects/{slug}", headers=admin)


def test_phase3_prompts_render():
    out = render(
        "interview_round.j2",
        kind_name="Tool paper",
        spec="",
        plan="",
        kind_rounds="## Round 1",
        playbook="",
        previous="",
    )
    assert "first round" in out and "has not written a specification" in out
    out = render(
        "research_plan.j2",
        kind_name="Tool paper",
        mode="explore",
        kind_notes="k",
        checklist="c",
        playbook_eval="",
        idea="idea",
        spec="",
    )
    assert "FIND A DIRECTION" in out and "=== THE IDEA ===" in out
    out = render(
        "outline.j2",
        kind_name="Tool paper",
        title="T",
        target_words=5000,
        structure="",
        kind_sections="s",
        spec="spec",
        plan="",
        interview="",
        facts="",
    )
    assert "# Outline: T" in out and "5000 words" in out
    out = render("facts.j2", spec="s", plan="", interview="")
    assert "# Facts" in out
    out = render("chat_system.j2", kind_name="Tool paper", title="T", spec="", plan="", interview="")
    assert "PIN:" in out
