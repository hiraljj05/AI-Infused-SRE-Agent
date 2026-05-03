---
id: RB-FRONTEND-CPU
kind: runbook
service: web-frontend
title: web-frontend CPU saturation
---

## Symptoms

- `web-frontend` pod CPU usage > 90%.
- P99 latency degrades.
- Error rate may still be low.

## Remediation

- `scale_deployment` to add replicas. Safe up to 5 replicas in this cluster (HIL-2 above 3).
- If CPU spike follows a deploy, `rollback_deployment` (HIL-2).
- If spike is caused by attack pattern (same source IPs), escalate to security.
