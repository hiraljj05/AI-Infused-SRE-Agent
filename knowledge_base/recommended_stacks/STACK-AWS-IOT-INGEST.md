---
id: STACK-AWS-IOT-INGEST
kind: recommended_stack
title: AWS IoT ingest + telemetry stack
cloud: aws
workload: iot
scale: growth
---

# AWS IoT ingest stack

## Edge → cloud ingest
- **AWS IoT Core** as the MQTT broker (no self-managed brokers)
- **IoT Greengrass** for edge compute, **IoT Device Defender** for fleet auditing
- Per-device X.509 certs rotated via **IoT Core Just-in-Time Provisioning**

## Stream processing
- **Kinesis Data Streams** for real-time pipelines
- **Kinesis Data Firehose** → S3/OpenSearch for archival + search
- **Lambda** for stateless transforms; **MSK (Kafka)** if you need >24h retention or replay

## Storage
- **Timestream** for time-series metrics
- **DynamoDB** for device state (low-latency single-key lookups)
- **S3 + Athena** for cold analytics

## Observability
- **CloudWatch IoT metrics** (connect/disconnect rate, message rate per topic)
- **Custom dashboard** for fleet health: % of devices online, rolling 24h message count
- Synthetic device probes from multiple regions

## Operational concerns
- **Device shadow** for offline-tolerant state sync
- **Topic-based authorization** (devices publish only to `things/+/telemetry`)
- Batch device firmware updates via **IoT Jobs**
- Capacity: provision Kinesis shards for 5× peak ingest (back-pressure during incidents is brutal)
