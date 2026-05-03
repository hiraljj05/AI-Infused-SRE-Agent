---
id: STACK-AWS-WEB-GROWTH
kind: recommended_stack
title: AWS web/API stack for growth-stage companies
cloud: aws
workload: web,api
scale: growth
---

# AWS web/API stack — growth scale

## Hosting
- **EKS** with Karpenter for node provisioning (mix of Spot + On-Demand)
- **ALB Ingress Controller** for ingress, **CloudFront** in front for global cache + WAF
- **Route 53** weighted routing for blue/green at DNS layer

## Observability
- **Amazon Managed Prometheus (AMP)** + **Amazon Managed Grafana (AMG)**
- **CloudWatch Logs** + **OpenSearch Service** for full-text search
- **AWS X-Ray** for distributed tracing (OTLP via ADOT collector)
- **Datadog APM** if budget permits — best signal-to-noise

## CI/CD
- **GitHub Actions** with OIDC to assume IAM roles (no long-lived keys)
- **Argo CD** + **Argo Rollouts** for canary/blue-green deployments
- **ECR** for images, scanned by Inspector

## Alerting
- **PagerDuty** for paging, **Slack** for context, both fed by **CloudWatch Alarms** + Prometheus Alertmanager
- SLO burn-rate alerts on the 5 golden signals
- **Statuspage.io** for customer comms

## Security
- **IRSA (IAM Roles for Service Accounts)** instead of node IAM
- **Secrets Manager** + **External Secrets Operator** in cluster
- **GuardDuty** + **Security Hub** for threat detection

## Data layer
- **RDS Aurora PostgreSQL** Multi-AZ with read replicas
- **ElastiCache Redis cluster** for hot data
- **S3 + Lambda** for async pipelines
