from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_admin
from ..llm.base import PURPOSES, LLMError, Message
from ..llm.registry import build_adapter, complete
from ..models import Provider, PurposeAssignment, User, now
from ..schemas import (
    LlmTestIn,
    LlmTestOut,
    ModelOut,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
    PurposeAssign,
    PurposeOut,
)
from ..security import encrypt_secret, key_hint, llm_limiter

router = APIRouter(prefix="/api", tags=["providers"])

PRESETS = [
    {"name": "OpenAI", "adapter": "openai_compat", "base_url": None},
    {"name": "OpenRouter", "adapter": "openai_compat", "base_url": "https://openrouter.ai/api/v1"},
    {"name": "Anthropic", "adapter": "anthropic", "base_url": None},
    {"name": "Groq", "adapter": "openai_compat", "base_url": "https://api.groq.com/openai/v1"},
    {"name": "Mistral", "adapter": "openai_compat", "base_url": "https://api.mistral.ai/v1"},
    {"name": "DeepSeek", "adapter": "openai_compat", "base_url": "https://api.deepseek.com/v1"},
    {"name": "Together", "adapter": "openai_compat", "base_url": "https://api.together.xyz/v1"},
    {
        "name": "Gemini (OpenAI endpoint)",
        "adapter": "openai_compat",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
    {"name": "Ollama (local)", "adapter": "openai_compat", "base_url": "http://host.docker.internal:11434/v1"},
]


def _out(p: Provider) -> ProviderOut:
    return ProviderOut(
        id=p.id,
        name=p.name,
        adapter=p.adapter,
        base_url=p.base_url,
        has_key=bool(p.api_key_enc),
        key_hint=p.key_hint,
        enabled=p.enabled,
        models=[ModelOut(**m) for m in (p.models_cache or [])],
        models_fetched_at=p.models_fetched_at,
        models_error=p.models_error,
        created_at=p.created_at,
    )


async def _refresh_models(p: Provider) -> None:
    try:
        models = await build_adapter(p).list_models()
        p.models_cache = [{"id": m.id, "name": m.name, "context_window": m.context_window} for m in models]
        p.models_error = None
    except LLMError as e:
        p.models_error = str(e)[:1000]
    except Exception as e:  # network, auth, timeouts
        p.models_error = f"{type(e).__name__}: {e}"[:1000]
    p.models_fetched_at = now()


@router.get("/providers/presets")
def presets(_: User = Depends(require_admin)):
    return PRESETS


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [_out(p) for p in db.scalars(select(Provider).order_by(Provider.created_at)).all()]


@router.post("/providers", response_model=ProviderOut, status_code=201)
async def create_provider(body: ProviderCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Provider).where(Provider.name == body.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A provider with that name already exists")
    p = Provider(name=body.name, adapter=body.adapter, base_url=body.base_url or None)
    if body.api_key:
        p.api_key_enc = encrypt_secret(body.api_key)
        p.key_hint = key_hint(body.api_key)
    db.add(p)
    db.commit()
    await _refresh_models(p)
    db.commit()
    return _out(p)


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: str, body: ProviderUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    p = db.get(Provider, provider_id)
    if not p:
        raise HTTPException(404, "Provider not found")
    key_changed = False
    if body.name is not None and body.name != p.name:
        if db.scalar(select(Provider).where(Provider.name == body.name)):
            raise HTTPException(status.HTTP_409_CONFLICT, "A provider with that name already exists")
        p.name = body.name
    if body.base_url is not None:
        p.base_url = body.base_url or None
        key_changed = True
    if body.api_key is not None:
        if body.api_key == "":
            p.api_key_enc = None
            p.key_hint = None
        else:
            p.api_key_enc = encrypt_secret(body.api_key)
            p.key_hint = key_hint(body.api_key)
        key_changed = True
    if body.enabled is not None:
        p.enabled = body.enabled
    db.commit()
    if key_changed:
        await _refresh_models(p)
        db.commit()
    return _out(p)


@router.post("/providers/{provider_id}/refresh-models", response_model=ProviderOut)
async def refresh_models(provider_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(Provider, provider_id)
    if not p:
        raise HTTPException(404, "Provider not found")
    await _refresh_models(p)
    db.commit()
    return _out(p)


@router.delete("/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.get(Provider, provider_id)
    if not p:
        raise HTTPException(404, "Provider not found")
    db.delete(p)
    db.commit()


# ---------------------------------------------------------------- purposes


@router.get("/purposes", response_model=list[PurposeOut])
def list_purposes(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    out = []
    for purpose, description in PURPOSES.items():
        a = db.get(PurposeAssignment, purpose)
        prov = a.provider if a and a.provider_id else None
        out.append(
            PurposeOut(
                purpose=purpose,
                description=description,
                provider_id=prov.id if prov else None,
                provider_name=prov.name if prov else None,
                model=a.model if a else None,
            )
        )
    return out


@router.put("/purposes/{purpose}", response_model=PurposeOut)
def assign_purpose(purpose: str, body: PurposeAssign, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if purpose not in PURPOSES:
        raise HTTPException(404, "Unknown purpose")
    prov = None
    if body.provider_id:
        prov = db.get(Provider, body.provider_id)
        if not prov:
            raise HTTPException(404, "Provider not found")
    a = db.get(PurposeAssignment, purpose)
    if not a:
        a = PurposeAssignment(purpose=purpose)
        db.add(a)
    a.provider_id = prov.id if prov else None
    a.model = body.model if prov else None
    db.commit()
    return PurposeOut(
        purpose=purpose,
        description=PURPOSES[purpose],
        provider_id=a.provider_id,
        provider_name=prov.name if prov else None,
        model=a.model,
    )


@router.post("/llm/test", response_model=LlmTestOut)
async def test_purpose(body: LlmTestIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not llm_limiter.allow(admin.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down")
    started = time.perf_counter()
    try:
        result = await complete(
            db, body.purpose, [Message("user", body.prompt)], user_id=admin.id, max_tokens=100, temperature=0.2
        )
    except LLMError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    from ..llm.registry import resolve

    r = resolve(db, body.purpose)
    return LlmTestOut(
        ok=True,
        provider=r.provider.name,
        model=result.model,
        text=result.text.strip(),
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
