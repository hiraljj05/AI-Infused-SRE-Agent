from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str
    structured: dict[str, Any] | None = None


class LLMPort(Protocol):
    async def complete(
        self,
        *,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        ...

    async def complete_structured(
        self,
        *,
        messages: list[LLMMessage],
        json_schema: dict[str, Any],
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        ...
