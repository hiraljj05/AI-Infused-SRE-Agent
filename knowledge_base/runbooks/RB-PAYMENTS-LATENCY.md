---
id: RB-PAYMENTS-LATENCY
kind: runbook
service: payments-api
title: payments-api p99 latency degradation
---

## Symptoms

- `http_request_duration_seconds:p99` on `payments-api` exceeds 1500ms.
- Upstream services (`orders-api`, `web-frontend`) show cascading latency.
- Error rate may remain normal.

## Likely causes

1. Network latency between `payments-api` and `inventory-db`.
2. Resource contention (noisy neighbour on node).
3. Recent config change increasing retry/backoff windows.

## Verification

1. Check `container_cpu_usage_seconds_total:rate` for the pod's node.
2. Measure round-trip latency to `inventory-db` from `payments-api`.
3. Review recent ConfigMap / Secret updates for the service.

## Remediation

- If the node is pressured: `scale_deployment` to move load off the hot node
  (HIL-2 required because of blast radius).
- If network-related: rollout restart to re-shuffle pods across nodes.
- If config regression: `rollback_deployment` to the last known good revision.
