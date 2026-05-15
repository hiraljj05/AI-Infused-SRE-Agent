#  AI Infused SDLC SRE Agent

##  Overview

Modern production systems run 24/7, and when incidents happen — especially during late nights or peak traffic hours — engineers are required to manually investigate logs, metrics, dashboards, and infrastructure health to identify the issue and resolve it.


This process is often repetitive, time-consuming, and stressful.
For recurring incidents, engineers may end up performing the same troubleshooting steps multiple times, including:


* Checking Grafana dashboards
* Analyzing Prometheus metrics
* Reading logs from Loki/ELK
* Identifying root causes
* Executing fixes manually
* Creating incident reports and postmortems


The AI Infused SDLC SRE Agent automates this operational workflow using AI-driven monitoring, incident analysis, remediation, and learning systems.


The agent continuously monitors infrastructure and applications in real time. 

When an issue is detected, it:
* Collects metrics and logs automatically
* Performs intelligent Root Cause Analysis (RCA)
* Searches memory for similar historical incidents
* Uses predefined operational playbooks (rulebooks) for known issues
* Executes automated remediation when confidence is high
* Escalates risky incidents to engineers when needed
* Generates incident timelines and postmortem data automatically

This significantly reduces:
* Mean Time To Recovery (MTTR)
* Manual operational effort
* Repetitive debugging work
* Downtime during critical incidents

The system acts as an intelligent SRE assistant that improves reliability, accelerates incident response, and continuously learns from previous failures.

---

##  Key Features

*  Continuous infrastructure and application monitoring
*  Real-time anomaly and spike detection
*  Parallel multi-channel alerting (Jira, Email, Teams)
*  Automated incident creation and classification
*  Automated Root Cause Analysis (RCA)
*  Automated remediation using playbooks
*  Confidence-based decision making
*  Human-in-the-Loop (HIL) for critical actions
*  Memory-based learning from historical incidents
*  SLA tracking and escalation management
*  Automatic postmortem generation
*  Cloud + On-Prem observability support
*  Advisory mode for new infrastructure/system design
*  Self-healing operational workflows

  
##  System Architecture


<img width="827" height="504" alt="image" src="https://github.com/user-attachments/assets/eabbb5fe-6602-480f-9aa3-a85d6ce4b049" />
<img width="1311" height="751" alt="image" src="https://github.com/user-attachments/assets/cca41cc1-16fa-4a04-9ab2-34ffb7b0cab1" />
<img width="1561" height="539" alt="image" src="https://github.com/user-attachments/assets/22922124-e246-40ba-886f-fef19a3475e5" />
<img width="1260" height="707" alt="image" src="https://github.com/user-attachments/assets/ce63a704-7761-4bac-8bbf-76f00fcdbffd" />


##  End-to-End Workflow

### 1. Monitoring & Data Collection

The agent continuously monitors metrics, logs, and dashboards across cloud and on-premise environments.

**Supported Monitoring Sources**

**On-Premise**
* ELK Stack → Grafana
 
**Cloud**
* Azure Monitor
* Cloud-native observability platforms

**Local Metrics**
* Prometheus → Metrics collection
* Promtail + Loki → Log aggregation

Grafana acts as the centralized observability layer for all monitoring systems.

---

### 2. Incident Detection

The agent detects:

* Threshold breaches
* CPU spikes
* Memory spikes
* OOMKilled containers
* Service downtime
* High latency
* Pod crashes

Features
* Deduplicates repeated alerts
* Prevents alert storms
* Uses predefined thresholds from dashboards

---

### 3. Alerting (Parallel Execution)

When an incident is detected, alerts are triggered simultaneously.

**Alert Channels:**
* Jira ticket creation
* Microsoft Teams / Slack notifications
* Email alerts to stakeholders

This ensures faster incident visibility and response.

---

### 4. Incident Classification

| Priority | Severity | Description              |
| -------- | -------- | ------------------------ |
| P0       | Critical | Complete production outage  |
| P1       | High     | Major service degradation       |
| P2       | Medium   | Partial functionality issue   |
| P3       | Low      | Minor/non-critical issue |

---

### 5. SLA-Driven Incident Management

The system tracks SLA deadlines automatically.

* **Acknowledgement (Ack):**

  * P0/P1 → within ~2–5 minutes

* **Root Cause Analysis (RCA):**

  * P0/P1 → within ~10–30 minutes
 
**Features:**

* RCA added directly into Jira tickets
* Automatic SLA breach escalation
* Escalation tracking and monitoring

---

### 6. Escalation

* Escalation is based on priority (P0–P3)
* Can escalate to:

  * Another agent
  * DevOps engineer (Human-in-the-loop)

---

### 7. Root Cause Analysis (RCA)

**The agent performs intelligent RCA using:**

* Historical incidents
* Logs and metrics
* Rulebooks / Playbooks
* Similar past failures
* Infrastructure signals
  
**Before RCA:**

The system searches memory for:

* Similar incidents
* Previous RCA reports
* Successful fixes
* Resolver history

---
**What is a Rulebook / Playbook?**

A playbook (rulebook) is a collection of predefined operational fixes for common production issues.

**Examples:**

* Restart crashed pods
* Increase memory limits
* Restart unhealthy deployments
* Scale deployments during traffic spikes
* Clear failed jobs/queues

When a similar incident occurs again, the agent can automatically execute the validated fix instead of requiring engineers to manually repeat the same troubleshooting process.

This enables faster recovery and self-healing infrastructure.

---

### 8. Decision & Remediation

The agent decides actions using confidence-based decision making.

#### High Confidence

* Automatically executes remediation playbooks

#### Low Confidence

* Routes to **Human-in-the-Loop(HIL)** approval

#### Unknown Incidents

* Attempts autonomous resolution
* Learns from outcome

---
**Human-in-the-Loop (HIL)**

Critical or risky actions require manual approval.

**Examples:**

* Production scaling changes
* Infrastructure modifications
* Risky deployment restarts
* Database-impacting actions

Approval notifications are sent through Teams.

---

### 9. Change Management

Every remediation is classified as:

* **HOTFIX / RISKY**

  * Requires manual approval

* **SAFE / RECURRING**

  * Auto-executed
    
* **Validation Checks**

  * Baseline monitoring
  * Post-fix verification
  * Rollback handling

---

### 10. Fix Validation

**After remediation:**

* Metrics are re-checked
* Logs are analyzed again
* System health is validated
* Baseline performance is compared

If the issue still exists:

* Incident workflow restarts automatically

---

### 11. Memory & Learning System

The system continuously learns from previous incidents.

**Stored Knowledge:**

* Issue type (4xx, 5xx, latency, crash, etc.)
* Root cause
* Resolution steps
* Resolver (agent or human) information
* Incident timelines
* Recovery Patterns

**Benefits**

For future incidents, the agent can:

* Suggest previous fixes
* Recommend probable RCA
* Reduce debugging time
* Improve remediation accuracy

---
**Postmortem Generation**

After incident resolution, the agent automatically generates postmortem data.

**Stored in PostgreSQL**

* Incident summary
* Root cause
* Timeline of events
* Metrics involved
* Actions taken
* Resolution details
* SLA breach information
* Learning outcomes

This creates a complete operational history for future analysis and auditing.

---

### 12. Data Storage & Traceability

The platform uses PostgreSQL as the primary operational database.

**Stored Data**

* Incidents
* RCA reports
* Playbook execution logs
* Approvals
* Escalation history
* SLA tracking
* Postmortems
* Event timelines


**Vector Memory**

The system also uses:
* pgvector
* Qdrant

for semantic similarity search and memory retrieval.

---

### 13. Advisory / Consulting Mode

The agent can also act as an intelligent SRE consultant for new systems.

**Capabilities:**

**Infrastructure Recommendations**

  * Cloud vs On-Prem setup
  * Monitoring stack selection
  * Deployment recommendations

**Scaling Guidance**
   
Examples:

  * Scaling systems from 2 → 800 cameras
  * GPU infrastructure planning
  * High-load architecture recommendations

**Observability Guidance**

* Latency monitoring
* GPU utilization tracking
* Memory monitoring
* Network health analysis

---

##  Tech Stack

| Layer        | Technology                         |
| ------------ | ---------------------------------- |
| Backend      | FastAPI                            |
| Monitoring   | Prometheus, Grafana, Azure Monitor |
| Logging      | Promtail, Loki, ELK                |
| Database     | PostgreSQL                         |
| Vector Search| pgvector/Qdrant                    |
| Containerization| Docker                          |
| Orchestration | Kubernetes(AKS)                   |
| Alerting     | Jira, Email, Teams                 |
| Cloud        | Microsoft Azure                    |

---

**Cloud Infrastructure**

The project is deployed using:

* Azure Kubernetes Service (AKS)
* Azure Bot Service
* Azure Entra ID
* Azure Log Analytics Workspace
* Docker-based microservices

---

**Scalability**

The platform is designed for enterprise-scale operations.

**Scaling Features**

* Kubernetes autoscaling
* Distributed workers
* Redis caching
* Async FastAPI APIs
* Queue-based processing
* Multi-user concurrent support

**Security**

* Role-based access control
* Human approval for risky actions
* Secure Teams bot communication
* JWT-secured APIs
* Audit logging and traceability

---

##  Project Objective

To build an intelligent AI-powered SRE system that:

* Detects incidents in real time
* Automates operational workflows
* Reduces manual effort
* Improves Mean Time To Recovery (MTTR)
* Learns continuously from operational history
* Acts as both an operator and infrastructure advisor

---

**Future Enhancements**

* Advanced multi-agent workflows
* Predictive incident prevention
* Distributed tracing with OpenTelemetry
* Autonomous infrastructure optimization
* Multi-tenant SaaS architecture
* Voice-enabled operational assistant
* AI-driven cost optimization
  
---
