---
id: STACK-AZURE-WEB-STARTUP
kind: recommended_stack
title: Azure web/API stack for startups
cloud: azure
workload: web,api
scale: startup
---

# Azure web/API stack — startup scale

## Hosting
- **AKS Standard tier** with 2-3 Standard_B2s_v2 nodes (auto-scale 2→6)
- Ingress via **NGINX ingress controller** + **cert-manager** for Let's Encrypt
- DNS through Azure DNS, SSL termination at ingress

## Observability
- **Prometheus + Grafana** (kube-prometheus-stack Helm chart, single-node)
- **Loki** for logs (single binary mode)
- **OpenTelemetry Collector** sidecar for traces → **Tempo**
- **Azure Monitor Container Insights** as backup for control-plane metrics

## CI/CD
- **GitHub Actions** for build + push to **Azure Container Registry**
- **Argo CD** in pull mode for cluster sync
- **Helm** for templating, **Kustomize** for overlays per env

## Alerting
- Prometheus Alertmanager → **Microsoft Teams** webhook + **PagerDuty Free** for after-hours
- SLO-based alerts only (golden signals: latency, errors, traffic, saturation)
- Quiet hours configured for non-P1

## Secrets
- **Azure Key Vault** + **Sealed Secrets** for git-stored secrets

## Capacity baseline
- HPA on CPU 70% / Memory 80%
- KEDA for event-driven workloads
- Pod Disruption Budgets minAvailable: 1
