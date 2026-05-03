---
id: INC-SAMPLE-001
kind: incident
service: payments-api
title: "2026-03-14 payments-api 503 spike from processor outage"
---

## Summary

Third-party payment processor experienced a 12-minute outage. Our `/charge` handler
returned 503s to `orders-api`, which cascaded to `web-frontend`.

## RCA

Confirmed cause: upstream processor. Our circuit breaker opened correctly but fell back
to retrying every 2 seconds, which amplified client-side errors. Retry interval was
subsequently tuned to exponential backoff with jitter.

## Corrective actions

- JIRA-4201: tune circuit-breaker retry policy
- JIRA-4202: add dashboard panel for external processor SLA compliance

## What the SRE Agent would do today

Detect the error-rate spike, diagnose as "upstream dependency failure" with supporting
evidence from logs. Because remediation requires a config change, agent proposes
`no_op_escalate` and notifies DBA/payments SME.
