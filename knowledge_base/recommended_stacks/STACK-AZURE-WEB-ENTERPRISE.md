---
id: STACK-AZURE-WEB-ENTERPRISE
kind: recommended_stack
title: Azure web/API stack for enterprise scale
cloud: azure
workload: web,api
scale: enterprise
---

# Azure web/API stack — enterprise scale

## Hosting
- **AKS Premium tier** with multi-AZ node pools (System + User pools, 3+ AZs)
- **Azure Front Door** (Premium) for global L7 + WAF + DDoS Standard
- **Application Gateway Ingress Controller (AGIC)** for in-cluster ingress
- Multi-region active-passive with **Traffic Manager** failover

## Observability
- **Managed Prometheus (Azure Monitor for Prometheus)** + **Azure Managed Grafana**
- **Azure Monitor Logs (Log Analytics)** with KQL alerts
- **Application Insights** for distributed tracing (OTLP-compatible)
- **Datadog or Dynatrace** as a secondary pane if budget allows
- Long-term retention: 90 days hot, 1 year cold in Storage Account

## CI/CD
- **Azure DevOps** or **GitHub Enterprise Actions** with environment approvals
- **Argo CD** with App-of-Apps + ApplicationSets for fleet management
- **Helm** charts in private registry, signed with Cosign

## Alerting
- Multi-tier: PagerDuty (P1/P2) + ServiceNow ticketing + Teams channels
- SLO burn-rate alerts (multi-window, multi-burn-rate per Google SRE workbook)
- Synthetic checks via **Azure Front Door Health Probes** + **Pingdom**

## Security & Compliance
- **Azure Policy** + **Gatekeeper/OPA** in cluster
- **Defender for Containers** for runtime threat detection
- **Private cluster** (no public API endpoint), JIT access via Privileged Identity Management
- **Azure AD Workload Identity** instead of pod-managed identity

## Capacity baseline
- HPA + VPA + Cluster Autoscaler
- Reserved Instances or Savings Plans for 70% of baseline
- Capacity tests quarterly, chaos engineering monthly (Azure Chaos Studio)
