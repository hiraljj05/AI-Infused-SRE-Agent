---
id: RB-PAYMENTS-503
kind: runbook
service: payments-api
title: payments-api returning 503s
---

## Symptoms

- Error rate on `payments-api` exceeds 5% with 503 status codes dominating.
- `orders-api` begins returning 502s upstream.
- No corresponding CPU or memory pressure on `payments-api` pods.

## Likely causes

1. Transient failure in a dependency (payment processor circuit breaker open).
2. Recent deployment introducing a bug in the `/charge` handler.
3. In-pod admin failure flag accidentally left enabled (dev / chaos only).

## Verification steps

1. Check recent deployments on `payments-api` (within the last hour).
2. Inspect pod logs for the literal string `payment processor unavailable` (chaos signature).
3. Check error rate on downstream dependencies: `inventory-db` connections, processor webhook.

## Remediation

- If dependency is healthy and no recent deploy: restart a single `payments-api` pod
  (`restart_pod`) to clear transient in-pod state.
- If recent deploy correlates: `rollback_deployment` to previous revision (HIL-2 required).
- If admin flag is set in dev: hit `/_admin/heal` on the service.

## Verification after remediation

Error rate returns to baseline (<= 1%) within 2 minutes. P99 latency should also normalize.
