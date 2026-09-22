"""Resolve a purpose to a concrete provider + model and run logged completions.

Resolution chain: section override -> project override -> purpose default.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import LlmCall, Project, Provider, PurposeAssignment
from ..security import decrypt_secret
from .anthropic_adapter import AnthropicAdapter
from .base import PURPOSES, Completion, LLMAdapter, LLMError, Message
from .openai_compat import OpenAICompatAdapter

ADAPTERS = {
    "openai_compat": OpenAICompatAdapter,
    "anthropic": AnthropicAdapter,
}


def build_adapter(provider: Provider) -> LLMAdapter:
    cls = ADAPTERS.get(provider.adapter)
    if cls is None:
        raise LLMError(f"Unknown adapter '{provider.adapter}'")
    api_key = decrypt_secret(provider.api_key_enc) if provider.api_key_enc else None
    return cls(api_key=api_key, base_url=provider.base_url)


@dataclass
class Resolved:
    provider: Provider
    model: str
    source: str  # "section" | "project" | "purpose"


def resolve(db: Session, purpose: str, project: Project | None = None, section: str | None = None) -> Resolved:
    if purpose not in PURPOSES:
        raise LLMError(f"Unknown purpose '{purpose}'")

    overrides = (project.model_overrides or {}) if project else {}
    # Overrides look like {"draft": {"provider_id": "...", "model": "..."},
    #                      "sections": {"introduction": {"provider_id": "...", "model": "..."}}}
    if section:
        sec = (overrides.get("sections") or {}).get(section)
        if sec and sec.get("provider_id") and sec.get("model"):
            prov = db.get(Provider, sec["provider_id"])
            if prov and prov.enabled:
                return Resolved(prov, sec["model"], "section")
    proj = overrides.get(purpose)
    if proj and proj.get("provider_id") and proj.get("model"):
        prov = db.get(Provider, proj["provider_id"])
        if prov and prov.enabled:
            return Resolved(prov, proj["model"], "project")

    assignment = db.get(PurposeAssignment, purpose)
    if not assignment or not assignment.provider_id or not assignment.model:
        raise LLMError(f"No model assigned for purpose '{purpose}'. Ask an admin to set one in Settings.")
    prov = db.get(Provider, assignment.provider_id)
    if not prov or not prov.enabled:
        raise LLMError(f"Provider for purpose '{purpose}' is missing or disabled.")
    return Resolved(prov, assignment.model, "purpose")


async def complete(
    db: Session,
    purpose: str,
    messages: list[Message],
    *,
    project: Project | None = None,
    section: str | None = None,
    user_id: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    json_mode: bool = False,
) -> Completion:
    """Run one completion for a purpose and record it in llm_calls."""
    resolved = resolve(db, purpose, project, section)
    adapter = build_adapter(resolved.provider)
    started = time.perf_counter()
    call = LlmCall(
        purpose=purpose,
        provider_id=resolved.provider.id,
        provider_name=resolved.provider.name,
        model=resolved.model,
        project_id=project.id if project else None,
        user_id=user_id,
    )
    try:
        result = await adapter.complete(
            resolved.model, messages, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode
        )
        call.input_tokens = result.usage.input_tokens
        call.output_tokens = result.usage.output_tokens
        call.cached_tokens = result.usage.cached_tokens
        call.ok = True
        return result
    except LLMError as e:
        call.ok = False
        call.error = str(e)[:2000]
        raise
    finally:
        call.duration_ms = int((time.perf_counter() - started) * 1000)
        db.add(call)
        db.commit()
