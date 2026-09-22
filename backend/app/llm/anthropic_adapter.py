"""Anthropic Messages API adapter."""

from __future__ import annotations

from anthropic import APIError, AsyncAnthropic

from .base import Completion, LLMError, Message, ModelInfo, Usage


class AnthropicAdapter:
    def __init__(self, api_key: str | None, base_url: str | None = None):
        self._client = AsyncAnthropic(api_key=api_key or "no-key", base_url=base_url or None, max_retries=2)

    async def complete(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> Completion:
        system_parts = [m.content for m in messages if m.role == "system"]
        chat = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        system = "\n\n".join(system_parts) if system_parts else None
        if json_mode:
            system = (system + "\n\n" if system else "") + "Respond with a single valid JSON object and nothing else."
        kwargs: dict = {
            "model": model,
            "messages": chat,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            # Stable prefix is placed in the system block so provider prompt caching applies.
            kwargs["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        try:
            resp = await self._client.messages.create(**kwargs)
        except APIError as e:
            raise LLMError(str(e)) from e
        text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        usage = Usage(
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cached_tokens=getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
        )
        return Completion(text=text, model=resp.model, usage=usage, stop_reason=resp.stop_reason)

    async def list_models(self) -> list[ModelInfo]:
        try:
            page = await self._client.models.list(limit=100)
        except APIError as e:
            raise LLMError(str(e)) from e
        models = [ModelInfo(id=m.id, name=getattr(m, "display_name", None)) for m in page.data]
        models.sort(key=lambda x: x.id)
        return models
