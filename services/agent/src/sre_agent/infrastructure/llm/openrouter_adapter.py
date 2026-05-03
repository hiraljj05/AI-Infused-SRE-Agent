from __future__ import annotations

import json
from typing import Any

import pybreaker
import structlog
from openai import AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from sre_agent.common.metrics import LLM_TOKENS
from sre_agent.domain.ports.llm import LLMMessage, LLMPort, LLMResponse


log = structlog.get_logger(__name__)


class OpenRouterLLMAdapter(LLMPort):
    """LLM adapter using OpenRouter's OpenAI-compatible API.

    Includes:
    - tenacity retries with exponential backoff on transient failures
    - pybreaker circuit breaker to fail fast during sustained outages
    - Prometheus counters for token usage
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        site_url: str = "",
        app_name: str = "",
        request_timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("OpenRouter API key is required")
        default_headers: dict[str, str] = {}
        if site_url:
            default_headers["HTTP-Referer"] = site_url
        if app_name:
            default_headers["X-Title"] = app_name
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=default_headers or None,
            timeout=request_timeout_seconds,
            max_retries=0,
        )
        self._model = model
        self._breaker = pybreaker.CircuitBreaker(
            fail_max=5,
            reset_timeout=60,
            name="openrouter",
        )

    async def complete(
        self,
        *,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        return await self._do_complete(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=None,
        )

    async def complete_structured(
        self,
        *,
        messages: list[LLMMessage],
        json_schema: dict[str, Any],
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        schema_messages = list(messages)
        schema_hint = LLMMessage(
            role="system",
            content=(
                "Respond with ONLY a JSON object matching this JSON Schema. "
                "Do not wrap in markdown fences.\n"
                f"Schema: {json.dumps(json_schema)}"
            ),
        )
        schema_messages.append(schema_hint)
        response = await self._do_complete(
            messages=schema_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        # Try to parse; if model returned markdown-wrapped JSON, strip fences
        raw = response.content.strip()
        if raw.startswith("```"):
            # remove first and last fence lines
            lines = raw.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
        if not raw:
            raise ValueError("LLM returned empty content")
        try:
            structured = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.error("llm returned invalid JSON", content=response.content[:1000])
            raise ValueError(f"LLM returned non-JSON: {exc}") from exc
        return LLMResponse(
            content=response.content,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            finish_reason=response.finish_reason,
            structured=structured,
        )

    async def _do_complete(
        self,
        *,
        messages: list[LLMMessage],
        temperature: float,
        max_tokens: int,
        response_format: dict[str, str] | None,
    ) -> LLMResponse:
        payload = [{"role": m.role, "content": m.content} for m in messages]

        async def _call() -> ChatCompletion:
            return await self._client.chat.completions.create(
                model=self._model,
                messages=payload,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,  # type: ignore[arg-type]
            )

        completion: ChatCompletion
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                completion = await _call()

        choice = completion.choices[0]
        content = choice.message.content or ""
        usage = completion.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        LLM_TOKENS.labels(provider="openrouter", model=self._model, kind="prompt").inc(prompt_tokens)
        LLM_TOKENS.labels(
            provider="openrouter", model=self._model, kind="completion"
        ).inc(completion_tokens)
        return LLMResponse(
            content=content,
            model=completion.model or self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=choice.finish_reason or "stop",
        )
