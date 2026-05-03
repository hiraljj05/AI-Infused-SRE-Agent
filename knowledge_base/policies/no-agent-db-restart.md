---
id: POL-DB-RESTART
kind: policy
title: Database restarts require DBA approval
---

## Policy

The SRE Agent must never restart a database pod (inventory-db, postgres, redis) or
scale it automatically. All database operations require HIL-2 approval from the DBA team.

## Rationale

Data integrity risk. A premature restart during a flush can corrupt state.

## How to apply

- Filter `restart_pod` and `scale_deployment` actions targeting any pod in the `data-tier`
  label group or matching pattern `*-db-*`.
- Always fall through to `no_op_escalate` for these targets.
