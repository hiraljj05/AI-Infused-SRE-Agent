---
id: STACK-AZURE-DATA-PIPELINE
kind: recommended_stack
title: Azure data-pipeline / batch ETL stack
cloud: azure
workload: data-pipeline,batch
scale: growth
---

# Azure data pipeline stack

## Compute
- **Azure Data Factory** for orchestration of cross-system pipelines
- **Databricks** (or **Synapse Spark Pools**) for transformation jobs
- **AKS with KEDA** for event-driven workers (Kafka/Service Bus consumers)
- **Azure Functions** (Premium plan) for short, parallelizable transforms

## Storage
- **ADLS Gen2** as the data lake (raw / staged / curated zones)
- **Synapse Dedicated SQL Pool** or **Snowflake on Azure** for the warehouse
- **Cosmos DB** for low-latency lookups in pipelines

## Observability
- **Azure Monitor** + **Log Analytics** queries via KQL
- **Pipeline-level SLOs**: freshness, completeness, schema validity
- **Great Expectations** or **Soda Cloud** for data quality assertions
- Metrics surfaced in **Power BI** dashboards for stakeholders

## Orchestration & lineage
- **Apache Airflow** on AKS for code-defined DAGs (alt: Data Factory)
- **OpenLineage** + **Marquez** for lineage tracking

## Alerting
- Tiered: data quality breach → DataOps Slack; pipeline failure → PagerDuty
- Schema drift detection alerts
- Cost alerts per-pipeline (Synapse pools are expensive)

## Compliance
- **Purview** for cataloging + classification (PII tagging mandatory if HIPAA/PCI in scope)
- Row-level security and column masking in Synapse
