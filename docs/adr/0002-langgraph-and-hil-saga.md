# ADR-0002: LangGraph for Agent Orchestration, Saga for HIL

- Status: accepted
- Date: 2026-04-22

## Context

The agent's decision flow is a multi-step reasoning loop:
detect -> triage -> gather -> retrieve -> diagnose -> plan -> classify risk ->
(HIL interrupt) -> execute -> verify -> document.

BRD BR-020-004 mandates HIL-2 approval for any high-impact production action. Approvals
can take seconds (trivial) or hours (off-hours on-call). The agent must not hold state
in RAM — the backend may restart mid-approval.

## Decision

- Use **LangGraph** to model the state machine. Each node is a well-defined step with
  typed inputs/outputs.
- Use LangGraph's **checkpointer** with Postgres backing for durable state. When the
  graph encounters a `NOTIFY_HIL` node, it invokes `interrupt_before=["execute"]`.
  The run persists; the process may die.
- Resume via an inbound webhook that carries the `approval_id` correlating to the
  paused run. Inject the decision and continue the graph.
- Wrap the approval lifecycle as a **Saga**:
  - `PENDING -> NOTIFIED_PRIMARY -> NOTIFIED_SECONDARY -> ESCALATED_TO_COMMANDER -> DEAD_LETTER`
  - Each transition emits a domain event. Scheduled compensating actions fire on timeout.
- Idempotency: every approval request has a `uuid4` key. Duplicate webhook deliveries
  are short-circuited.

## Consequences

Positive:
- Durable approval state — survives restarts and crashes.
- Clear graph structure is visualisable and explainable to SRE leads.
- Saga semantics make escalation and timeouts explicit and testable.
- Audit trail naturally falls out of saga state transitions.

Negative:
- LangGraph still evolving; we pin version and encapsulate behind `AgentPort` so we can
  swap later if needed.
- Postgres checkpointer adds a hard dependency on DB availability for agent
  invocation.
