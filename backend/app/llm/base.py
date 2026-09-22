"""Provider-neutral LLM interface.

Two adapters (OpenAI-compatible and Anthropic) implement this. Nothing outside the
`llm` package should import a provider SDK directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]

PURPOSES: dict[str, str] = {
    "learn": "Reads exemplar papers and author sources to build playbooks and profiles. "
    "Wants long context and careful reading.",
    "interview": "Asks clarifying questions and drafts suggested answers. Wants good judgement and tool calling.",
    "draft": "Writes and rewrites sections. Wants the strongest writing model you have.",
    "critique": "Acts as a venue reviewer and checks facts across sections. Wants strong reasoning.",
    "utility": "Summaries, ranking search results, extraction, figure descriptions. "
    "Wants cheap and fast; vision helps.",
}


@dataclass
class Message:
    role: Role
    content: str


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class Completion:
    text: str
    model: str
    usage: Usage = field(default_factory=Usage)
    stop_reason: str | None = None


@dataclass
class ModelInfo:
    id: str
    name: str | None = None
    context_window: int | None = None


class LLMAdapter(Protocol):
    async def complete(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> Completion: ...

    async def list_models(self) -> list[ModelInfo]: ...


class LLMError(RuntimeError):
    pass
