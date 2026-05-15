#  AI Infused SDLC SRE Agent



##  Overview

Modern production systems run 24/7, and when incidents happen — especially during late nights or peak traffic hours — engineers are required to manually investigate logs, metrics, dashboards, and infrastructure health to identify the issue and resolve it.

This process is often repetitive, time-consuming, and stressful.
For recurring incidents, engineers may end up performing the same troubleshooting steps multiple times, including:

Checking Grafana dashboards
Analyzing Prometheus metrics
Reading logs from Loki/ELK
Identifying root causes
Executing fixes manually
Creating incident reports and postmortems

The AI Infused SDLC SRE Agent automates this operational workflow using AI-driven monitoring, incident analysis, remediation, and learning systems.

The agent continuously monitors infrastructure and applications in real time. When an issue is detected, it:

Collects metrics and logs automatically
Performs intelligent Root Cause Analysis (RCA)
Searches memory for similar historical incidents
Uses predefined operational playbooks (rulebooks) for known issues
Executes automated remediation when confidence is high
Escalates risky incidents to engineers when needed
Generates incident timelines and postmortem data automatically

This significantly reduces:

Mean Time To Recovery (MTTR)
Manual operational effort
Repetitive debugging work
Downtime during critical incidents

The system acts as an intelligent SRE assistant that improves reliability, accelerates incident response, and continuously learns from previous failures.
---

##  Key Capabilities

*  Continuous monitoring across on-prem and cloud environments
*  Real-time anomaly and spike detection
*  Parallel multi-channel alerting (Jira, Email, Chat)
*  Intelligent incident classification (P0–P3)
*  SLA-driven incident management (Ack, RCA, Escalation)
*  Automated Root Cause Analysis (RCA)
*  Self-healing using rulebooks (playbooks)
*  Confidence-based decision making
*  Human-in-the-Loop (HIL) for critical actions
*  Change management with approval workflows
*  Memory-driven learning and recommendations
*  Centralized incident logging and traceability
*  Advisory / consulting capability for new systems


##  System Architecture


<img width="827" height="504" alt="image" src="https://github.com/user-attachments/assets/eabbb5fe-6602-480f-9aa3-a85d6ce4b049" />
<img width="1311" height="751" alt="image" src="https://github.com/user-attachments/assets/cca41cc1-16fa-4a04-9ab2-34ffb7b0cab1" />
<img width="1561" height="539" alt="image" src="https://github.com/user-attachments/assets/22922124-e246-40ba-886f-fef19a3475e5" />
<img width="1260" height="707" alt="image" src="https://github.com/user-attachments/assets/ce63a704-7761-4bac-8bbf-76f00fcdbffd" />


##  End-to-End Workflow

### 1. Monitoring & Data Collection

The agent continuously monitors dashboards where metrics and thresholds are already defined.

Supported monitoring paths:

* **On-Premise**

  * ELK stack feeds into Grafana
* **Cloud**

  * Azure Monitor (or equivalent cloud monitoring tools)
* **Local Metrics**

  * Prometheus (metrics)
  * Promtail + Loki (logs)

Grafana acts as the **primary observation layer**.

---

### 2. Incident Detection

* Detects threshold breaches and abnormal spikes
* Deduplicates repeated signals into a single incident
* Uses dashboard-defined thresholds (does not create its own)

---

### 3. Alerting (Parallel Execution)

On incident detection, the agent triggers:

*  Jira ticket creation
*  Notification to project-specific channel (Teams/Slack)
*  Email to stakeholders

All alerts are executed **in parallel**.

---

### 4. Incident Classification

| Priority | Severity | Description              |
| -------- | -------- | ------------------------ |
| P0       | Critical | Complete system failure  |
| P1       | High     | Major system issue       |
| P2       | Medium   | Partial degradation      |
| P3       | Low      | Minor/non-critical issue |

---

### 5. SLA-Driven Incident Management

After ticket creation:

* **Acknowledgement (Ack):**

  * P0/P1 → within ~2–5 minutes

* **Root Cause Analysis (RCA):**

  * P0/P1 → within ~10–30 minutes

* RCA is posted directly in the same Jira ticket

* If SLA is breached → **auto escalation triggered**

---

### 6. Escalation

* Escalation is based on priority (P0–P3)
* Can escalate to:

  * Another agent
  * DevOps engineer (Human-in-the-loop)

---

### 7. Root Cause Analysis (RCA)

* Uses:

  * Historical incidents (memory)
  * Rulebooks (runbooks)

* Before analysis:

  * Agent checks memory for similar incidents
  * Suggests:

    * Previous RCA
    * Who resolved it
    * Possible fixes

---

### 8. Decision & Remediation

The agent decides based on **confidence score**:

#### High Confidence

* Auto-executes fix from playbook

#### Low Confidence

* Routes to **Human-in-the-Loop (HIL)**

#### New Issues

* Attempts autonomous resolution
* Learns from outcome

---

### 9. Change Management

Each fix is classified as:

* **HOTFIX / RISKY**

  * Requires human approval before execution

* **RECURRING**

  * Auto-executed
  * Must pass internal validation (QA-like check) before production

---

### 10. Fix Validation

After applying a fix:

* System is re-monitored
* Metrics are validated against baseline
* If unresolved → re-trigger incident flow

---

### 11. Memory & Learning System

Every incident is stored with:

* Issue type (4xx, 5xx, latency, crash, etc.)
* Root cause
* Resolution
* Resolver (agent or human)

On new incidents:

* Agent checks memory first
* Suggests similar past solutions

---

### 12. Incident Storage & Traceability

All data is stored in **PostgreSQL**, including:

* Incident details
* Severity
* RCA
* Resolution steps
* Escalation history
* Event logs with timestamps

---

### 13. Advisory / Consulting Mode

The agent also acts as an **SRE consultant** for new projects.

Capabilities include:

* Recommends monitoring stack based on:

  * Cloud vs on-prem
  * Project type

* Asks intelligent questions:

  * Infrastructure setup
  * Metrics availability
  * Deployment type

* Example scenarios:

  * Suggests tools for new system setup
  * Advises on scaling (e.g., 2 → 800 cameras)
  * Recommends GPU usage for high workloads
  * Suggests monitoring metrics (latency, GPU usage, network health)

* Provides guidance on:

  * Network latency checks
  * System connectivity
  * Observability best practices

---

##  Tech Stack

| Layer        | Technology                         |
| ------------ | ---------------------------------- |
| Monitoring   | Prometheus, Grafana, Azure Monitor |
| Logging      | Promtail, Loki, ELK                |
| Alerting     | Jira, Email, Teams/Slack           |
| Database     | PostgreSQL                         |
| Intelligence | AI Agent + Rulebook System         |

---

##  Objective

To build an intelligent SRE system that:

* Detects and resolves incidents in real time
* Reduces manual operational effort
* Ensures faster recovery and reliability
* Continuously improves through learning
* Acts as both an operator and an advisor

---
