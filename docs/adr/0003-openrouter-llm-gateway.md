# ADR-0003: OpenRouter as the LLM Gateway

- Status: accepted
- Date: 2026-04-22

## Context

The agent needs LLM capability for RCA reasoning, postmortem generation, and natural
language queries. We need model flexibility (try Claude vs GPT vs Llama for RCA
quality), cost control, and no Azure OpenAI quota dependency (adds days).

## Decision

- Use **OpenRouter** as the LLM gateway. Call it via the `openai` Python SDK with
  `base_url="https://openrouter.ai/api/v1"`.
- Abstract behind `LLMPort`. Default model via `OPENROUTER_MODEL` env
  (`anthropic/claude-3.5-sonnet` initially).
- Embeddings are **not** delegated to OpenRouter; use local `sentence-transformers`
  (`all-MiniLM-L6-v2`, 384 dims, CPU inference) to stay free and avoid Azure OpenAI
  provisioning.

## Consequences

Positive:
- Single provider, pay-per-use, no quota requests.
- Easy A/B across models for RCA quality testing.
- Works identically in dev and prod.

Negative:
- Another third-party dependency in the critical path.
- Different models have different strengths; RCA prompts may need per-model tuning.

Mitigations:
- Circuit breaker on the adapter — on repeated failures, return a low-confidence
  fallback response and mark incidents for human triage.
- Cache last-known-good response for identical prompts for chat-style NL queries.
