# ADR-0001: Hexagonal Architecture (Ports and Adapters)

- Status: accepted
- Date: 2026-04-22

## Context

The SRE Agent must integrate with many volatile dependencies (LLM providers, Kubernetes
distributions, observability platforms, messaging channels). Business logic — incident
triage, severity classification, RCA confidence evaluation, HIL routing — must not be
tied to any specific technology choice. BRD-020 enumerates many supported platforms
(Prometheus, Datadog, Grafana, Splunk, ELK, New Relic, Dynatrace, AppDynamics) implying
adapters will need to grow over time without rewriting core logic.

## Decision

Adopt Hexagonal Architecture:

- `domain/` contains entities, value objects, domain events, exceptions, and **ports**
  (Python `Protocol` classes defining outbound interfaces). No third-party runtime imports.
- `application/` contains use cases and the LangGraph state machine. Depends only on
  ports from `domain/`. No imports from `infrastructure/` or `interface/`.
- `infrastructure/` contains **adapters** — concrete implementations of ports using
  specific technologies (OpenRouter, Qdrant, Kubernetes, Prometheus, etc.).
- `interface/` contains driving adapters — FastAPI routers, Teams bot handlers, webhook
  endpoints, CLI. Translates transport inputs into use case calls.
- Dependency injection wiring lives in `composition_root.py`.

Boundaries enforced in CI by `import-linter`.

## Consequences

Positive:
- Domain logic is unit-testable with trivial fakes.
- LLM provider swap (OpenRouter -> Azure OpenAI -> local) is a one-file change.
- BRD's multi-platform observability requirement is achievable by adding adapters.
- Auditable: all side effects pass through explicit ports.

Negative:
- More files, more indirection than a script.
- Developers must learn the boundary rules (`import-linter` will teach them on first
  violation).

## Alternatives rejected

- Flat layout (service modules calling each other): fast initially, rots as integrations multiply.
- Django-style app with heavy ORM coupling: domain becomes invisible, RCA logic mixed
  with SQL.
- Microservices: overkill for single team, introduces network failures into the agent's
  own decision loop.
