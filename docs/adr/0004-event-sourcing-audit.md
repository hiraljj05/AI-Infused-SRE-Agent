# ADR-0004: Event-Sourced Audit Trail for Incidents

- Status: accepted
- Date: 2026-04-22

## Context

BRD NFR-09 requires "Full audit logs for all detection, RCA, remediation, escalation,
and resolution activities; immutable, tamper-evident, retained 36 months." BRD
NFR-12 requires every RCA confidence score to be traceable to source signals.

## Decision

Every mutation to an `Incident` aggregate is expressed as a domain event and appended
to an `incident_events` table. Current state is a fold over events. The `Incident`
aggregate is reconstructed on demand or via materialised read views (CQRS-lite) for
dashboard queries.

Events include:
- `IncidentDetected`, `IncidentTriaged`, `EvidenceGathered`, `RCAGenerated`,
  `ActionProposed`, `ApprovalRequested`, `ApprovalGranted`, `ApprovalRejected`,
  `ApprovalTimedOut`, `ActionExecuted`, `ActionVerified`, `IncidentResolved`,
  `PostmortemDrafted`.

Schema per event:
- `event_id` (uuid, PK)
- `incident_id` (uuid, FK)
- `event_type` (text, indexed)
- `occurred_at` (timestamptz, indexed)
- `correlation_id` (uuid) — the agent run ID
- `causation_id` (uuid, nullable) — the event that caused this one
- `payload` (jsonb) — event-specific data
- `created_by` (text) — "agent", "user:<email>", "system"

Append-only by DB convention (no UPDATE/DELETE grants on application role).

## Consequences

Positive:
- Full audit trail, replayable.
- Time-travel queries for forensic analysis.
- Can replay historical incidents against new LLM models for regression testing.
- Natural input for postmortem generation — timeline writes itself.

Negative:
- Aggregate reconstitution is slower than row-read. Mitigate with snapshots or CQRS
  read tables.
- Schema evolution of events needs versioning (`event_type` should carry a version).
