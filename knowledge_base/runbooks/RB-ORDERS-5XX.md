---
id: RB-ORDERS-5XX
kind: runbook
service: orders-api
title: orders-api 5xx cascade from payments-api
---

## Symptoms

- `orders-api` error rate rises in lock-step with `payments-api`.
- Customer-facing checkout flow failing.

## Diagnosis

1. Check if `payments-api` is the primary failing dependency (very likely).
2. If so, divert the agent's focus to the `payments-api` incident; `orders-api` is a victim.

## Remediation

- Fixing the `payments-api` incident resolves this one automatically.
- If `orders-api` has an independent bug: `rollback_deployment` (HIL-2).
