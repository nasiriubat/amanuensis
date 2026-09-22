"""OpenAI-compatible adapter.

Covers OpenAI, OpenRouter, Ollama, Groq, Together, Mistral, DeepSeek, Gemini's OpenAI
endpoint and any custom base URL that speaks /v1/chat/completions.
"""

from __future__ import annotations

from openai import APIError, AsyncOpenAI

from .base import Completion, LLMError, Message, ModelInfo, Usage


class OpenAICompatAdapter:
    def __init__(self, api_key: str | None, base_url: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key or "no-key", base_url=base_url or None, max_retries=2)

    async def complete(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> Completion:
        kwargs: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except APIError as e:
            raise LLMError(str(e)) from e
        choice = resp.choices[0]
        usage = Usage()
        if resp.usage:
            usage.input_tokens = resp.usage.prompt_tokens or 0
            usage.output_tokens = resp.usage.completion_tokens or 0
            details = getattr(resp.usage, "prompt_tokens_details", None)
            if details is not None:
                usage.cached_tokens = getattr(details, "cached_tokens", 0) or 0
        return Completion(
            text=choice.message.content or "",
            model=resp.model or model,
            usage=usage,
            stop_reason=choice.finish_reason,
        )

    async def list_models(self) -> list[ModelInfo]:
        try:
            page = await self._client.models.list()
        except APIError as e:
            raise LLMError(str(e)) from e
        models: list[ModelInfo] = []
        for m in page.data:
            name = getattr(m, "name", None)
            ctx = getattr(m, "context_length", None)  # OpenRouter exposes this
            models.append(ModelInfo(id=m.id, name=name, context_window=ctx))
        models.sort(key=lambda x: x.id)
        return models
