---
id: STACK-ONPREM-WEB
kind: recommended_stack
title: On-prem / hybrid web/API stack
cloud: on-prem
workload: web,api
scale: growth
---

# On-prem / hybrid stack

## Hosting
- **Rancher RKE2** or **OpenShift** for production-grade Kubernetes on-prem
- **MetalLB** for L2 load balancing, **NGINX Ingress** for HTTP
- **Longhorn** or **Portworx** for cloud-native storage (avoid hostPath)
- **OpenStack** or **VMware Tanzu** as the underlying IaaS

## Observability
- **Prometheus + Grafana + Loki + Tempo** all self-hosted (Helm)
- **Thanos** for long-term metric retention (S3-compatible — MinIO on-prem)
- **OpenSearch** for log search at scale

## CI/CD
- **GitLab CE/EE** with self-hosted runners (avoid public cloud egress costs)
- **Argo CD** for GitOps
- **Harbor** as private container registry with Notary signing

## Alerting
- **Alertmanager** → PagerDuty (paid, even for on-prem) or **Squadcast** (cheaper)
- Mail server: self-hosted **Postfix** or relay through SendGrid

## Backup & DR
- **Velero** for K8s cluster backups → S3-compatible target
- **Rsync** + **Restic** for file-level backups
- Off-site copy mandatory (different physical site or cloud cold storage)

## Pitfalls
- DNS / NTP / certificate management is YOUR problem — invest in automation early
- Keep a runbook for hardware failure scenarios (drives, NICs, rack switches)
- Capacity planning is harder — no elastic scale; over-provision by 30%
