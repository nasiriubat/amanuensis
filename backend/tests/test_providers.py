from app.llm.base import Message
from app.llm.registry import resolve


def test_provider_crud_and_secret_handling(client, admin):
    r = client.post(
        "/api/providers",
        headers=admin,
        json={
            "name": "Fake OpenAI",
            "adapter": "openai_compat",
            "base_url": "http://127.0.0.1:9/v1",
            "api_key": "sk-test-1234567890abcdef",
        },
    )
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["has_key"] is True and p["key_hint"] == "cdef"
    assert "api_key" not in p and "sk-test" not in r.text
    # model fetch against an unreachable URL records an error, does not crash
    assert p["models_error"] is not None
    assert p["models"] == []

    # assign purpose
    r = client.put("/api/purposes/draft", headers=admin, json={"provider_id": p["id"], "model": "gpt-x"})
    assert r.status_code == 200 and r.json()["model"] == "gpt-x"
    purposes = {x["purpose"]: x for x in client.get("/api/purposes").json()}
    assert purposes["draft"]["provider_name"] == "Fake OpenAI"
    assert purposes["learn"]["provider_id"] is None
    assert set(purposes) == {"learn", "interview", "draft", "critique", "utility"}

    # test endpoint fails cleanly (unreachable)
    r = client.post("/api/llm/test", headers=admin, json={"purpose": "draft"})
    assert r.status_code == 502
    r = client.post("/api/llm/test", headers=admin, json={"purpose": "learn"})
    assert r.status_code == 502 and "No model assigned" in r.json()["detail"]

    # the failed call was logged
    usage = client.get("/api/usage/summary").json()
    assert usage["total_calls"] >= 1
    assert usage["by_purpose"][0]["errors"] >= 1

    # clearing the key
    r = client.patch(f"/api/providers/{p['id']}", headers=admin, json={"api_key": ""})
    assert r.json()["has_key"] is False

    assert client.delete(f"/api/providers/{p['id']}", headers=admin).status_code == 204
    purposes = {x["purpose"]: x for x in client.get("/api/purposes").json()}
    assert purposes["draft"]["provider_id"] is None


def test_resolve_override_chain(client, admin):
    from app.db import SessionLocal
    from app.models import Project, Provider, PurposeAssignment

    with SessionLocal() as db:
        a = Provider(name="A", adapter="openai_compat")
        b = Provider(name="B", adapter="anthropic")
        db.add_all([a, b])
        db.flush()
        db.merge(PurposeAssignment(purpose="draft", provider_id=a.id, model="a-model"))
        db.commit()
        proj = Project(
            slug="x",
            title="x",
            owner_id="nobody",
            kind="other",
            model_overrides={
                "draft": {"provider_id": b.id, "model": "b-model"},
                "sections": {"intro": {"provider_id": a.id, "model": "a-intro"}},
            },
        )
        r = resolve(db, "draft")
        assert (r.provider.name, r.model, r.source) == ("A", "a-model", "purpose")
        r = resolve(db, "draft", proj)
        assert (r.provider.name, r.model, r.source) == ("B", "b-model", "project")
        r = resolve(db, "draft", proj, section="intro")
        assert (r.provider.name, r.model, r.source) == ("A", "a-intro", "section")
        db.delete(a)
        db.delete(b)
        db.commit()


def test_message_dataclass():
    m = Message("user", "hi")
    assert m.role == "user"
