---
id: STACK-MULTI-CLOUD-COMPLIANCE
kind: recommended_stack
title: Multi-cloud compliance-first stack (HIPAA / PCI-DSS / SOC2)
cloud: multi
workload: web,api
scale: enterprise
compliance: HIPAA,PCI-DSS,SOC2
---

# Compliance-first multi-cloud stack

Targets HIPAA, PCI-DSS, SOC 2 Type II audit readiness from day one.

## Hosting
- **Kubernetes per cloud** (AKS / EKS / GKE) with identical Helm baselines
- **Cilium CNI** with network policies (default-deny, explicit allow-list)
- **Private clusters only** — no public API endpoints
- **CIS Kubernetes Benchmark** enforcement via **kube-bench** + **Polaris**

## Identity
- **Workload Identity Federation** (Azure AD / IAM OIDC / GCP) — no long-lived service account keys
- **Step CA** for short-lived TLS (mTLS via service mesh)
- Privileged access via **Teleport** with audit recording

## Service mesh & encryption
- **Istio** or **Linkerd** with **mTLS strict** mode cluster-wide
- All data **encrypted at rest** with customer-managed keys (CMK)
- TLS 1.2+ everywhere, HSTS preload

## Observability + audit
- **Falco** for runtime security events → SIEM
- **Loki** with audit logs separated from app logs (different retention: 7 yrs for HIPAA)
- **OpenTelemetry** with PII redaction processor
- **OPA Gatekeeper** policy violations → SIEM

## Secrets
- **HashiCorp Vault** (HA, auto-unseal) — dynamic credentials only
- No secrets in env vars — all injected via Vault Agent Sidecar

## Compliance evidence collection
- **Drata** or **Vanta** for continuous evidence collection
- **AWS Config / Azure Policy / GCP Security Command Center** as the source-of-truth

## Backup & DR
- 3-2-1 backup rule: 3 copies, 2 media, 1 off-site
- Quarterly DR drills with documented RPO/RTO
- Immutable backups (object lock) for ransomware resilience
