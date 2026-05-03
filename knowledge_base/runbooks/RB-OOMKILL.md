---
id: RB-OOMKILL
kind: runbook
service: "*"
title: OOMKilled pods
---

## Symptoms

- Pod events contain `OOMKilled` reason.
- `container_memory_working_set_bytes` shows sustained growth to the limit.
- Restart count climbing.

## Likely causes

1. Memory leak in application.
2. Legitimate load beyond provisioned limits.
3. Misconfigured JVM / Node heap size.

## Remediation

- Short-term: `scale_deployment` horizontally to reduce per-pod memory pressure (HIL-2).
- Medium-term: raise memory limits — requires a manifest change via the DevOps Agent,
  not the SRE Agent.
- Long-term: open a Jira corrective action to investigate leak.
