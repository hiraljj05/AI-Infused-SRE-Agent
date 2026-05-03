---
id: RB-POD-CRASHLOOP
kind: runbook
service: "*"
title: Pod in CrashLoopBackOff
---

## Symptoms

- Pod phase is `CrashLoopBackOff`.
- `restart_count` grows monotonically.
- Service availability drops proportionally to affected replicas.

## Diagnosis

1. `get_pod_logs` with `previous=true` on the crashing pod to see the fatal error.
2. Inspect container exit code: 137 = OOM, 139 = segfault, 1 = application error.
3. Check recent image pull events — could be `ImagePullBackOff` masquerading.

## Remediation paths

- **Application bug after deploy**: `rollback_deployment` to last healthy revision (HIL-2).
- **OOM (exit 137)**: `scale_deployment` up to relieve pressure, or increase memory limits
  via a configuration change (HIL-2). Agent must not edit manifests directly.
- **Transient (env/config)**: `restart_pod` to clear state; escalate if recurs within 5 minutes.
