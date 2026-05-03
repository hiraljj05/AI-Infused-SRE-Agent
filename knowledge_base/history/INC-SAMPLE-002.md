---
id: INC-SAMPLE-002
kind: incident
service: orders-api
title: "2026-02-28 orders-api OOMKill after image update"
---

## Summary

`orders-api` deployed a new container image that raised baseline memory from 180MB to 420MB.
Memory limit was still 256MB, causing OOMKill on every 2-3 requests. Detected in 1m 54s.

## RCA

Deploy-time regression. Memory limit not updated alongside image change.

## Fix

Rolled back via agent `rollback_deployment` after HIL-2 approval. Filed JIRA-4188 to
update limits in Helm values.

## Pattern to remember

OOMKill within 5 minutes of a deploy almost always points to the deploy as the cause.
