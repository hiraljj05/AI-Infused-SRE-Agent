# SRE Agent Platform

Production-grade AI-powered Site Reliability Engineering agent. Monitors Kubernetes workloads,
detects incidents via multi-signal correlation, performs RCA with LLM reasoning, and executes
pre-approved remediation playbooks with Human-in-the-Loop (HIL) validation via Microsoft Teams.

Implements BRD-020 (AI Infused SDLC SRE Agent).

## Architecture

Hexagonal architecture (ports & adapters). Domain core is pure Python, free of infrastructure
concerns. LangGraph orchestrates the agent state machine with Postgres-backed checkpointing
for durable HIL pauses.

```
Teams Bot / Dashboard / Chaos UI
              |
              v
   FastAPI (inbound adapters)
              |
              v
   LangGraph state machine  <-- Saga: HIL approval with timeouts + escalation
              |
              v
   Use Cases (application layer)
              |
              v
   Domain (pure: Incident, Service, Approval, ...)
              ^
              |
   Adapters: OpenRouter | Qdrant | Postgres | K8s | Prometheus | sentence-transformers | Teams
```

## Stack

| Layer | Tech |
|------|------|
| Language | Python 3.12 (agent), TypeScript (dashboard) |
| Agent | FastAPI + LangGraph + OpenRouter |
| Vector DB | Qdrant (self-hosted in AKS) |
| Embeddings | sentence-transformers (local CPU) |
| State DB | Postgres 16 (StatefulSet) |
| Observability | Prometheus + Loki + Grafana + OpenTelemetry |
| Orchestration | AKS (single node, B2s) |
| IaC | Bicep + Helm + Argo CD |
| Bot | Microsoft Teams via Bot Framework SDK |

## Repository layout

```
services/
  agent/               Python agent backend (hexagonal)
    src/sre_agent/
      domain/          Pure domain model + ports
      application/     Use cases + LangGraph + saga
      infrastructure/  Adapters implementing ports
      interface/       REST + Bot + Webhooks
  dashboard/           Next.js dashboard
  chaos-ui/            Streamlit chaos injection
  dummy-app/           4-service demo workload
infra/
  bicep/               Azure resources
  helm/                K8s charts
  argocd/              GitOps app manifests
  chaos-experiments/   Chaos Mesh CRDs
knowledge_base/        Seed RAG content
docs/adr/              Architecture Decision Records
scripts/               Dev + deployment helpers
```

## Quick start

```
make dev-up      # Bring up local stack via docker-compose
make test        # Run unit + integration tests
make lint        # Lint + type-check everything
make deploy-aks  # Deploy to AKS via Helm
```

See `docs/adr/` for design decisions and `docs/runbook.md` for operations.

## BRD traceability

Every BRD requirement (BR-020-001 through BR-020-006) maps to code modules — see
`docs/brd_traceability.md`
