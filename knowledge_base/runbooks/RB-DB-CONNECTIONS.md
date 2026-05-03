---
id: RB-DB-CONNECTIONS
kind: runbook
service: inventory-db
title: inventory-db connection pool exhaustion
---

## Symptoms

- Error logs on client services: `too many connections`, `connection refused`, `pool exhausted`.
- Error rate on all services that depend on `inventory-db` rises simultaneously.

## Remediation

- Agent MUST NOT restart the database. Restarting the DB is HIL-2 and only DBA can approve.
- Clear idle client connections by `rollout_restart` on the noisiest client service.
- Escalate to DBA team (dba@company.com) if pool stays saturated for >2 minutes.
