# SRE-chatbot — office laptop setup

The whole stack lives in **AKS** (Azure). The laptop only needs three CLIs and two auth tokens — there's nothing to build, no Helm to install, no Docker to run.

---

## 1. Install three CLIs

| Tool | Why | Windows install |
|---|---|---|
| **Azure CLI** (`az`) | Get cluster credentials, manage Azure resources | `winget install Microsoft.AzureCLI` |
| **kubectl** | Port-forward to dashboard / chaos-ui / agent / Grafana / Prometheus | `winget install Kubernetes.kubectl` |
| **ngrok** | Public tunnel for the Teams bot | `winget install Ngrok.Ngrok` |

Verify:
```bash
az --version
kubectl version --client
ngrok --version
```

---

## 2. One-time auth

```bash
# Sign in to the Azure tenant where the cluster lives
az login --tenant fc2665fb-3fe9-40b9-9213-8f931aa11ed5

# Make sure the right subscription is active
az account set --subscription "Azure subscription 1"

# Pull AKS kubeconfig into ~/.kube/config
az aks get-credentials -n sre-demo-aks -g sre-agent-demo --overwrite-existing

# Wire ngrok to your account (token from dashboard.ngrok.com → Your Authtoken)
ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>
```

Sanity check:
```bash
kubectl get pods -A
```
You should see `agent`, `dashboard`, `chaos-ui` in `sre-agent` namespace, `food-orders`/`portfolio-web` in `demo`, and `prometheus-server`/`loki-0`/`grafana`/`promtail` in `platform` — all `Running`.

---

## 3. Daily workflow

### Start the cluster (if stopped to save cost)
```bash
az aks start -n sre-demo-aks -g sre-agent-demo
az postgres flexible-server start -n sre-agent-pg -g sre-agent-demo
```

### Open 5 port-forwards (one terminal each, or use tmux/Windows Terminal tabs)
```bash
kubectl port-forward -n sre-agent svc/dashboard 3000:3000
kubectl port-forward -n sre-agent svc/chaos-ui  8501:8501
kubectl port-forward -n sre-agent svc/agent     8000:8000
kubectl port-forward -n platform  svc/grafana   3001:3000
kubectl port-forward -n platform  svc/prometheus-server 9090:80
```

### Start ngrok (one terminal, keep open)
```bash
ngrok http --url=unworkable-submedially-deandra.ngrok-free.dev 8000
```
> **Important:** the agent listens on **port 8000**. If you point ngrok at any other port, the Teams bot won't work. Also, your ngrok token can only hold one tunnel-claim at a time — stop ngrok on the home laptop before starting it on the office laptop.

### Open in your browser
| URL | What |
|---|---|
| http://localhost:3000 | Main dashboard (incidents, postmortems, knowledge, etc.) |
| http://localhost:8501 | Chaos Lab — buttons that break real AKS pods |
| http://localhost:8000/docs | Agent FastAPI Swagger |
| http://localhost:3001 | Grafana (anonymous viewer; admin/admin to edit) |
| http://localhost:9090 | Prometheus query UI |

### Stop everything (when you're done — saves money)
```bash
az aks stop -n sre-demo-aks -g sre-agent-demo
az postgres flexible-server stop -n sre-agent-pg -g sre-agent-demo
```

---

## 4. End-to-end test (proves it works)

1. Open `http://localhost:3000/incidents` and `http://localhost:8501` side-by-side
2. In Chaos UI: service = `food-orders` → click **Inject — OOMKill**
3. Within 5s a new `INC-...` appears on the dashboard
4. Watch the timeline: Detected → Triaged → EvidenceGathered → RCAGenerated → ActionProposed → ApprovalRequested
5. **Adaptive card lands in your Teams DM** with Approve / Reject buttons (assuming ngrok is running and you've DM'd the bot at least once from this account)
6. Click **Approve** in Teams
7. Agent runs `kubectl patch` → memory restored to 256Mi → verify passes → **status flips to resolved** → postmortem written
8. Open `http://localhost:3000/people` — your resolution is attributed
9. Open the Jira ticket — it transitioned to Done

---

## 5. What lives where

```
                    AKS cluster (sre-demo-aks, centralindia)
   ┌──────────────────────────────────────────────────────────────────┐
   │  Namespace platform           Namespace sre-agent                │
   │   ├─ Prometheus                ├─ agent (FastAPI, persistent     │
   │   ├─ kube-state-metrics        │   /app/data on managed disk)    │
   │   ├─ Loki                      ├─ dashboard (Next.js)            │
   │   ├─ Promtail (DaemonSet)      ├─ chaos-ui (Streamlit)           │
   │   └─ Grafana                   └─ judge (CronJob, every 6h)      │
   │                                                                  │
   │  Namespace demo                                                  │
   │   ├─ food-orders × 2 (apps nodepool, taint workload=apps)        │
   │   └─ portfolio-web × 2                                           │
   └──────────────────────────────────────────────────────────────────┘
                                   │
   ┌─────────────────┬─────────────┴────────────┬──────────────────┐
   │ ACR             │ Postgres flex            │ Bot Service      │
   │ sreagentacr...  │ sre-agent-pg             │ sre-agent-pt-... │
   │ (images)        │ (incidents, lessons,     │ (Teams bridge)   │
   │                 │  apps, projects, slas)   │                  │
   └─────────────────┴──────────────────────────┴──────────────────┘
                                   │
                            ngrok (your laptop)
                                   │
                              Microsoft Teams
```

The laptop only runs port-forwards + ngrok — nothing else.

---

## 6. Trouble?

| Symptom | Cause | Fix |
|---|---|---|
| `kubectl get pods` says `Unable to connect to the server` | AKS stopped, or kubeconfig stale | `az aks start ...`, then `az aks get-credentials ...` |
| Port-forward dies after a few minutes | kubectl idle SPDY timeout (Windows quirk) | Just restart the affected port-forward |
| Teams DM gives no reply | ngrok not running, OR pointing at wrong port (must be **8000**), OR you've never DM'd the bot from this Microsoft account | Start ngrok properly; DM the bot once before injecting chaos |
| Dashboard shows "No data" in Grafana iframe | Grafana port-forward died, or browser cached the old datasource | Refresh the dashboard tab; verify `localhost:3001` is up |
| Incident stuck at "Diagnosing" forever | Agent pod restarted between gather and diagnose (cache lost). Already mitigated in agent v12+, but if it happens, force-resolve from HIL Queue. | Click **Force resolve + restore** in `/hil` |
| `az ... firewall-rule create` complains about IP | Office laptop's public IP isn't whitelisted on Postgres | Only matters if you want direct DB access. The agent in AKS already has its own rule. |

---

## 7. Costs (FYI)

Running 24/7 ≈ **$1.80/day** (AKS B2s_v2 nodes + Postgres flex + ACR Basic). Stop AKS + Postgres when not actively demoing — drops to ~$0.20/day for ACR + idle storage.

---

## 8. Architecture quick refresher

- **Trigger** = chaos injection from Chaos UI (real `kubectl patch` on AKS deployment)
- **Detect → Triage → Gather → Diagnose → Propose** (LLM via OpenRouter Claude Sonnet 4.5) → **Notify HIL** (Teams adaptive card)
- **Approve in Teams** → agent runs `kubectl patch` to restore baseline → **Verify** (Prometheus check) → **Postmortem** (LLM 5-whys) → **Resolved** + Jira transitioned to Done + lesson recorded for People page
- **Judge** CronJob every 6h verifies the whole pipeline still works (regression guard)
- **Persistence**: Postgres for incidents/lessons/SLAs/approvals; ACR for images; managed disks for Loki/Prom/Grafana/Qdrant/agent-data; in-cluster Loki for logs (24h retention); in-cluster Prom for metrics (6h retention).

That's it.
