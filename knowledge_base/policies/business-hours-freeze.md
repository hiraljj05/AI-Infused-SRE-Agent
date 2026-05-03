---
id: POL-BUSINESS-HOURS-FREEZE
kind: policy
title: Business hours change freeze
---

## Policy

Between 09:00 and 17:00 local time on weekdays, the SRE Agent must NOT execute destructive
remediation (`rollback_deployment`, `scale_deployment` crossing 2x, `cordon_node`) without
HIL-2 approval, regardless of severity.

## Rationale

Customer traffic is highest during business hours. Recovery-from-bad-rollback times exceed
the cost of short outages during low-traffic windows.

## Exceptions

P1 incidents with blast_radius=CRITICAL AND SLO burn rate exceeding 24h may bypass this
policy via an Incident Commander override.
