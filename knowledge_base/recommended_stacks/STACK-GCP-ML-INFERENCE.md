---
id: STACK-GCP-ML-INFERENCE
kind: recommended_stack
title: GCP ML inference / model-serving stack
cloud: gcp
workload: ml
scale: growth
---

# GCP ML inference stack

## Hosting
- **GKE Autopilot** with GPU node pools (T4 for cost, A100 for throughput)
- Or **Vertex AI Endpoints** for fully-managed serving (lower ops, higher $/req)
- **KServe** or **Seldon Core** for in-cluster model serving
- **Cloud Run** for lightweight CPU-only models (autoscale to zero)

## Observability
- **Google Cloud Monitoring** + **Cloud Logging** (built-in for GKE)
- **NVIDIA DCGM Exporter** for GPU metrics → Prometheus
- **Vertex AI Model Monitoring** for drift detection
- Track p50/p95/p99 inference latency, queue depth, GPU utilization, batch size

## CI/CD
- **Cloud Build** triggered by GitHub
- **Artifact Registry** for container images, **Vertex AI Model Registry** for model versions
- Argo CD or **Cloud Deploy** for cluster sync

## Alerting
- Inference SLOs: p99 latency, error rate, queue depth, GPU utilization
- Cost alerts on per-endpoint token spend (critical for LLMs)
- **PagerDuty** integration via Cloud Monitoring

## Capacity
- **Horizontal Pod Autoscaler on QPS** (custom metric via Stackdriver Adapter)
- Maintain 1.5× peak capacity for ML latency (cold starts kill SLO)
- Pre-warm pools for burst traffic
