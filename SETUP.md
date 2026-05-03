# SRE Agent — Setup Guide

End-to-end setup for the SRE Agent platform. After completing this guide you'll have:

- Local stack (FastAPI agent + Next.js dashboard + Postgres + Qdrant + Loki + Grafana + Prometheus + 2 demo apps) running in Docker
- Real Azure Bot Service tied to a Microsoft Teams app for the bot interface
- Real Jira Cloud integration for incident tickets
- Real Azure Kubernetes Service (AKS) cluster the agent can read from + execute `kubectl` against
- ngrok tunnel exposing the agent's `/api/messages` endpoint to Microsoft Bot Framework

Total time: **45-60 minutes** (most of it waiting on Azure resource creation).

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Clone + env file](#2-clone--env-file)
3. [External accounts you need](#3-external-accounts-you-need)
4. [OpenRouter — LLM gateway](#4-openrouter--llm-gateway)
5. [Jira Cloud — ticketing](#5-jira-cloud--ticketing)
6. [Azure — AKS + AAD apps + Bot Service](#6-azure--aks--aad-apps--bot-service)
7. [ngrok — public tunnel for Teams bot](#7-ngrok--public-tunnel-for-teams-bot)
8. [Local stack — `docker compose up`](#8-local-stack--docker-compose-up)
9. [Seed data — projects, apps, knowledge base](#9-seed-data--projects-apps-knowledge-base)
10. [Deploy demo workloads to AKS](#10-deploy-demo-workloads-to-aks)
11. [Sideload Teams app](#11-sideload-teams-app)
12. [Verify everything](#12-verify-everything)
13. [Demo flow](#13-demo-flow)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Prerequisites

Install these on your machine first:

| Tool | Version | macOS install |
|---|---|---|
| **Docker Desktop** | 4.30+ | https://www.docker.com/products/docker-desktop |
| **Python 3** | 3.10+ (system Python is fine) | preinstalled on macOS |
| **kubectl** | 1.28+ | `brew install kubectl` |
| **Azure CLI** | 2.60+ | `brew install azure-cli` |
| **ngrok** | 3.x | `brew install --cask ngrok` |
| **Node.js** | 20+ (only needed if you want to run dashboard outside Docker) | `brew install node` |

Docker Desktop must be running before you start the local stack.

---

## 2. Clone + env file

```bash
git clone <your-repo-url> SRE-chatbot
cd SRE-chatbot
cp .env.example .env  # if .env.example exists; otherwise create .env from scratch (template below)
```

**Create `.env` at the repo root** with these variables. Replace every `REPLACE_ME` after going through the rest of this guide:

```bash
# ─── LLM (OpenRouter — see §4) ─────────────────────────────────────────
OPENROUTER_API_KEY=REPLACE_ME
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
OPENROUTER_SITE_URL=https://github.com/your-org/sre-agent
OPENROUTER_APP_NAME=SRE-Agent

# ─── Embeddings (sentence-transformers, runs in agent container) ─────
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDINGS_DIM=384

# ─── Persistence (defaults work for the dockerized stack) ────────────
POSTGRES_DSN=postgresql+asyncpg://sre:sre@localhost:5432/sre_agent
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=sre_knowledge

PROMETHEUS_URL=http://localhost:9090
LOKI_URL=http://localhost:3100

# ─── Kubernetes (AKS — see §6) ───────────────────────────────────────
K8S_IN_CLUSTER=false
TARGET_NAMESPACE=demo

# ─── Agent app config ────────────────────────────────────────────────
APP_ENV=dev
LOG_LEVEL=INFO
HTTP_PORT=8000
HIL_PRIMARY_TIMEOUT_SECONDS=60
HIL_SECONDARY_TIMEOUT_SECONDS=60
HIL_COMMANDER_TIMEOUT_SECONDS=120
RCA_CONFIDENCE_THRESHOLD=0.7
DEMO_FORCE_HIL=true                     # set false in production
INCIDENT_COMMANDER=@yourtenant.onmicrosoft.com
DEFAULT_ON_CALL_PRIMARY=demo@yourtenant.onmicrosoft.com
DEFAULT_ON_CALL_SECONDARY=@yourtenant.onmicrosoft.com
MAX_AUTO_REMEDIATION_BLAST_RADIUS=low

# ─── Jira Cloud (see §5) ─────────────────────────────────────────────
JIRA_BASE_URL=https://yourorg.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=REPLACE_ME
JIRA_PROJECT_KEY=SCRUM

KNOWLEDGE_BASE_ROOT=./knowledge_base

# ─── Microsoft Teams Bot (see §6.3) ──────────────────────────────────
MICROSOFT_APP_ID=REPLACE_ME
MICROSOFT_APP_PASSWORD=REPLACE_ME
MICROSOFT_APP_TENANT_ID=REPLACE_ME
MICROSOFT_APP_TYPE=SingleTenant

# ─── Dashboard OIDC sign-in (separate AAD app, see §6.4) ─────────────
AAD_TENANT_ID=common
AAD_CLIENT_ID=REPLACE_ME
AAD_CLIENT_SECRET=REPLACE_ME
AAD_REDIRECT_URI=http://localhost:8000/auth/callback
AAD_POST_LOGIN_REDIRECT=http://localhost:3030/
AUTH_SESSION_SECRET=change-me-generate-a-random-string
AUTH_ADMIN_EMAILS=you@example.com,demo@example.com
AUTH_REQUIRED=false
```

The `.env` is git-ignored — never commit it.

---

## 3. External accounts you need

Before continuing you need accounts at:

- **OpenRouter** (https://openrouter.ai) — LLM provider
- **Atlassian Jira Cloud** (https://www.atlassian.com/software/jira/free) — ticketing
- **Microsoft Azure** with at least one subscription (free tier works) — for AKS
- **Microsoft 365 / Entra tenant** (work or school account; personal Outlook does NOT work for Teams bots) — for the bot
- **ngrok** account (free tier) — for the public tunnel

---

## 4. OpenRouter — LLM gateway

1. Sign up at https://openrouter.ai
2. Add credits (~$5 is plenty for testing)
3. Settings → API Keys → **Create Key**
4. Copy the `sk-or-v1-…` key into `.env` as `OPENROUTER_API_KEY`

---

## 5. Jira Cloud — ticketing

1. Create a Jira Cloud site if you don't have one (free at https://www.atlassian.com/software/jira/free)
2. Create a project (Scrum template is fine). Note the **project key** (e.g. `SCRUM`).
3. Generate an API token:
   - Visit https://id.atlassian.com/manage-profile/security/api-tokens
   - **Create API token** → name it `sre-agent` → Copy.
4. Fill in `.env`:
   ```
   JIRA_BASE_URL=https://yourorg.atlassian.net   # NO trailing slash
   JIRA_EMAIL=your-email@example.com             # account that owns the token
   JIRA_API_TOKEN=ATATT3xFf...
   JIRA_PROJECT_KEY=SCRUM                        # the project key from step 2
   ```

---

## 6. Azure — AKS + AAD apps + Bot Service

### 6.1 Login + subscription

```bash
az login
az account list -o table
az account set --subscription "<your-subscription-name-or-id>"
```

### 6.2 Resource group + AKS cluster

```bash
RG=sre-agent-demo
LOCATION=centralindia       # or any region you prefer

az group create -n $RG -l $LOCATION

az aks create \
  --resource-group $RG \
  --name sre-demo-aks \
  --node-count 1 \
  --node-vm-size Standard_B2s_v2 \
  --enable-managed-identity \
  --generate-ssh-keys
```

Wait ~10 min for cluster creation.

### 6.3 Bot AAD app + secret + Bot Service

The Teams bot needs a **single-tenant** AAD app. **Switch your Azure CLI context to your M365 tenant first** (the one your Teams users live in):

```bash
az account set --subscription "N/A(tenant level account)"   # the Entra-only tenant entry
az account show --query tenantId -o tsv                     # confirm correct tenant
```

Create the bot AAD app + a 1-year client secret:

```bash
BOT_APP_ID=$(az ad app create \
  --display-name "sre-agent-bot" \
  --sign-in-audience AzureADMyOrg \
  --query "appId" -o tsv)

# Service principal — required so the app can be used in this tenant
az ad sp create --id $BOT_APP_ID

BOT_SECRET=$(az ad app credential reset \
  --id $BOT_APP_ID \
  --append --display-name "bot-secret" \
  --years 1 --query password -o tsv)

TENANT_ID=$(az account show --query tenantId -o tsv)
echo "MICROSOFT_APP_ID=$BOT_APP_ID"
echo "MICROSOFT_APP_PASSWORD=$BOT_SECRET"
echo "MICROSOFT_APP_TENANT_ID=$TENANT_ID"
```

**Save these three values immediately** — the secret is shown only once. Put them in `.env`.

Now create the Azure Bot Service. **Switch back to the subscription tenant** (Bot resource lives in a subscription, not just a directory):

```bash
az account set --subscription "<your-paid-subscription-id>"

# You need ngrok URL first — see §7. Replace <ngrok-id> below.
az bot create \
  --resource-group $RG \
  --name sre-agent-bot-$USER \
  --app-type SingleTenant \
  --appid $BOT_APP_ID \
  --tenant-id $TENANT_ID \
  --endpoint "https://<ngrok-id>.ngrok-free.dev/api/messages" \
  --sku F0
```

Add Microsoft Teams as a channel. The newer `az bot msteams create` is buggy; use `az rest`:

```bash
SUB=$(az account show --query id -o tsv)
az rest --method PUT \
  --url "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.BotService/botServices/sre-agent-bot-$USER/channels/MsTeamsChannel?api-version=2022-09-15" \
  --body '{
    "location":"global",
    "properties":{
      "channelName":"MsTeamsChannel",
      "properties":{"isEnabled":true,"acceptedTerms":true,"enableCalling":false}
    }
  }'
```

### 6.4 Dashboard OIDC AAD app (separate from bot)

The dashboard's "Sign in" button uses its own AAD app with a different sign-in audience (multi-tenant + personal accounts) so any Microsoft account can log in:

```bash
DASH_APP_ID=$(az ad app create \
  --display-name "sre-agent-platform" \
  --sign-in-audience AzureADandPersonalMicrosoftAccount \
  --web-redirect-uris "http://localhost:8000/auth/callback" \
  --query "appId" -o tsv)

DASH_SECRET=$(az ad app credential reset \
  --id $DASH_APP_ID \
  --append --display-name "dev-secret" \
  --years 1 --query password -o tsv)

echo "AAD_CLIENT_ID=$DASH_APP_ID"
echo "AAD_CLIENT_SECRET=$DASH_SECRET"
```

Put both into `.env` (`AAD_TENANT_ID=common` for multi-tenant).

### 6.5 Generate a kubeconfig with a scoped ServiceAccount

The agent runs `kubectl` against AKS. We use a dedicated ServiceAccount (NOT cluster-admin or your user creds) for least-privilege.

```bash
# Get a temporary kubeconfig for yourself
az aks get-credentials --resource-group $RG --name sre-demo-aks \
  --overwrite-existing --file /tmp/sre-demo-kubeconfig

# Apply the scoped ClusterRole + ServiceAccount + token Secret
KUBECONFIG=/tmp/sre-demo-kubeconfig kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Namespace
metadata: { name: demo }
---
apiVersion: v1
kind: ServiceAccount
metadata: { name: sre-agent, namespace: kube-system }
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: { name: sre-agent-operator }
rules:
  - apiGroups: [""]
    resources: ["pods","pods/log","events","nodes","namespaces","services","configmaps"]
    verbs: ["get","list","watch","delete"]
  - apiGroups: [""]
    resources: ["pods/exec"]
    verbs: ["create"]
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["patch"]
  - apiGroups: ["apps"]
    resources: ["deployments","deployments/scale","statefulsets","daemonsets","replicasets"]
    verbs: ["get","list","watch","patch","update"]
  - apiGroups: ["batch"]
    resources: ["jobs","cronjobs"]
    verbs: ["get","list","watch","delete"]
  - apiGroups: ["metrics.k8s.io"]
    resources: ["pods","nodes"]
    verbs: ["get","list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: { name: sre-agent-operator }
roleRef: { apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: sre-agent-operator }
subjects:
  - { kind: ServiceAccount, name: sre-agent, namespace: kube-system }
---
apiVersion: v1
kind: Secret
metadata:
  name: sre-agent-token
  namespace: kube-system
  annotations:
    kubernetes.io/service-account.name: sre-agent
type: kubernetes.io/service-account-token
YAML

# Build a SA-token-only kubeconfig (no exec plugin / no admin creds)
mkdir -p infra/k8s
KUBECONFIG=/tmp/sre-demo-kubeconfig python3 - <<'PY'
import base64, json, subprocess, time, yaml
for _ in range(15):
    out = subprocess.run(
        ["kubectl","-n","kube-system","get","secret","sre-agent-token","-o","json"],
        capture_output=True, text=True)
    data = json.loads(out.stdout).get("data", {})
    if data.get("token") and data.get("ca.crt"):
        break
    time.sleep(2)
ctx = json.loads(subprocess.run(
    ["kubectl","config","view","--raw","-o","json"],
    capture_output=True, text=True).stdout)
current = ctx["current-context"]
cluster = next(c["context"]["cluster"] for c in ctx["contexts"] if c["name"]==current)
server  = next(c["cluster"]["server"]   for c in ctx["clusters"]  if c["name"]==cluster)
kc = {
    "apiVersion":"v1","kind":"Config",
    "clusters":[{"name":"sre-demo-aks","cluster":{"server":server,"certificate-authority-data":data["ca.crt"]}}],
    "users":[{"name":"sre-agent","user":{"token":base64.b64decode(data["token"]).decode()}}],
    "contexts":[{"name":"sre-agent@sre-demo-aks","context":{"cluster":"sre-demo-aks","user":"sre-agent","namespace":"demo"}}],
    "current-context":"sre-agent@sre-demo-aks",
}
with open("infra/k8s/agent-kubeconfig.yaml","w") as f:
    yaml.safe_dump(kc, f)
print("wrote infra/k8s/agent-kubeconfig.yaml")
PY
```

The agent container mounts this file at `/app/kubeconfig.yaml` (already wired in `docker-compose.dev.yml`).

---

## 7. ngrok — public tunnel for Teams bot

Microsoft Bot Framework requires HTTPS. ngrok exposes our local agent.

```bash
# First time only — sign up at ngrok.com, get an authtoken
ngrok config add-authtoken <your-token>

# Start the tunnel (keep this running in its own terminal)
ngrok http 8000
```

Copy the `https://….ngrok-free.dev` URL. Use it as the `--endpoint` value in §6.3 (Bot Service create) and update `.env` if needed.

If you already created the bot with an old URL, update it:

```bash
az bot update \
  --resource-group sre-agent-demo \
  --name sre-agent-bot-$USER \
  --endpoint "https://<new-ngrok-id>.ngrok-free.dev/api/messages"
```

---

## 8. Local stack — `docker compose up`

With `.env` filled in:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

This starts 12 containers:

| Service | Port | What |
|---|---|---|
| `agent` | 8000 | FastAPI brain |
| `dashboard` | 3030 | Next.js UI |
| `postgres` | 5432 | incidents/approvals/lessons DB |
| `qdrant` | 6333 | vector search (RAG) |
| `redis` | 6379 | cache |
| `prometheus` | 9090 | metrics scrape |
| `grafana` | 3001 | viz (admin/admin) |
| `loki` | 3100 | log aggregation |
| `promtail` | — | ships docker logs to loki |
| `portfolio-web` | 8081 | Flask demo app #1 |
| `food-orders` | 8082 | Flask demo app #2 |
| `chaos-ui` | 8501 | Streamlit chaos panel (legacy, optional) |

Wait ~60s for everything to be healthy:

```bash
until curl -fs http://localhost:8000/healthz >/dev/null; do sleep 2; done && echo "agent up"
```

### 8.1 Database — schema & migrations

The agent uses **Postgres** (incidents, approvals, SLA trackers, lessons,
project/app registry) and **Qdrant** (vector store for the knowledge base
and lesson embeddings). Postgres comes up empty inside `sre-chatbot-postgres-1`
— the schema is managed by **Alembic**, with revisions in
`services/agent/src/sre_agent/infrastructure/persistence/migrations/versions/`.

Run migrations the first time (and after every `git pull` that adds a new revision).
The container doesn't ship `alembic.ini` (image is runtime-only), so copy it in once:

```bash
docker cp services/agent/alembic.ini sre-chatbot-agent-1:/app/alembic.ini
docker exec sre-chatbot-agent-1 sh -lc \
  "cd /app && POSTGRES_DSN=postgresql+asyncpg://sre:sre@postgres:5432/sre_agent \
   alembic -c /app/alembic.ini upgrade head"
```

> Quick patch (no Alembic) — apply a single column change directly when you don't
> want to author a migration:
> ```bash
> docker exec sre-chatbot-postgres-1 psql -U sre -d sre_agent -c \
>   "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS jira_ticket_key VARCHAR(64);"
> ```
>
> Generate a new migration from model changes:
> ```bash
> docker exec sre-chatbot-agent-1 sh -lc \
>   "cd /app && POSTGRES_DSN=postgresql+asyncpg://sre:sre@postgres:5432/sre_agent \
>    alembic -c /app/alembic.ini revision --autogenerate -m 'describe change'"
> ```

Verify schema:

```bash
docker exec sre-chatbot-postgres-1 psql -U sre -d sre_agent -c "\dt"
docker exec sre-chatbot-postgres-1 psql -U sre -d sre_agent -c "\d incidents"
```

You should see tables: `incidents`, `approvals`, `postmortems`, `incident_events`,
`projects`, `apps`, `sla_trackers`, `lessons_learnt`, `alembic_version`.
The `incidents` table has `jira_ticket_key` + `jira_ticket_url` columns
(revision `0003`) so the dashboard and Teams approval card can render a
clickable Jira link.

**Reset DB (demo only — keeps registry intact):**

```bash
docker exec sre-chatbot-postgres-1 psql -U sre -d sre_agent -c \
  "TRUNCATE incidents, approvals, postmortems, incident_events, sla_trackers, lessons_learnt CASCADE;"
```

**Qdrant collections** are created lazily on first agent boot (`ensure_collection()`
in the FastAPI lifespan hook). To wipe and re-seed the vector store:

```bash
docker exec sre-chatbot-qdrant-1 sh -lc 'rm -rf /qdrant/storage/* && echo wiped'
docker restart sre-chatbot-qdrant-1
# then re-run the seed step in 9.1
```

---

## 9. Seed data — projects, apps, knowledge base

### 9.1 Knowledge base into Qdrant

```bash
docker cp scripts/seed_knowledge_base.py sre-chatbot-agent-1:/tmp/seed.py
docker exec sre-chatbot-agent-1 sh -lc \
  "cd /app && PYTHONPATH=/app/src KNOWLEDGE_BASE_ROOT=/app/knowledge_base python /tmp/seed.py"
```

Loads runbooks, service catalogs, sample incidents, and recommended-stack templates into Qdrant.

### 9.2 Create a project

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "key": "CHK",
    "name": "Checkout Platform",
    "description": "Demo project",
    "jira_project_key": "SCRUM",
    "incident_commander_group": "@yourtenant.onmicrosoft.com"
  }'
```

Save the returned `id` (e.g. `proj_fca1483bd7d1`) — you'll need it for app onboarding.

### 9.3 Onboard the demo apps

```bash
PROJECT_ID=$(curl -s http://localhost:8000/api/projects | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

for SVC in portfolio-web food-orders; do
  curl -s -X POST http://localhost:8000/api/apps \
    -H "Content-Type: application/json" \
    -d "{
      \"project_id\":\"$PROJECT_ID\",
      \"name\":\"$SVC\",
      \"namespace\":\"demo\",
      \"tier\":\"tier-1\",
      \"owners\":[{\"email\":\"@example.com\",\"role\":\"primary\"}],
      \"runbook_template_id\":\"default-web-service\"
    }"
  echo
done
```

### 9.4 Provision per-app Grafana dashboards

```bash
docker exec sre-chatbot-agent-1 python -c "
import asyncio
from sre_agent.infrastructure.grafana import GrafanaAdapter
from sre_agent.infrastructure.grafana.grafana_adapter import build_app_dashboard_template

async def main():
    g = GrafanaAdapter(url='http://grafana:3000', username='admin', password='admin')
    for n in ['portfolio-web', 'food-orders', 'agent']:
        d = build_app_dashboard_template(app_name=n, namespace='demo')
        uid = await g.upsert_dashboard(d)
        print('  provisioned', uid)
    await g.close()
asyncio.run(main())
"
```

---

## 10. Deploy demo workloads to AKS

The agent reads pod state, restart counts, and OOM events from this real cluster. Apply the demo deployments:

```bash
KUBECONFIG=/tmp/sre-demo-kubeconfig kubectl apply -f - <<'YAML'
apiVersion: apps/v1
kind: Deployment
metadata: { name: food-orders, namespace: demo, labels: { app: food-orders } }
spec:
  replicas: 2
  selector: { matchLabels: { app: food-orders } }
  template:
    metadata: { labels: { app: food-orders } }
    spec:
      containers:
        - name: app
          image: python:3.12-slim
          command: ["python","-c"]
          args:
            - |
              import http.server, socketserver
              ballast = bytearray(100 * 1024 * 1024)
              print(f"food-orders booting; ballast={len(ballast)//1024//1024}MB", flush=True)
              class H(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                  self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
                def log_message(self,*a): pass
              with socketserver.TCPServer(("",8080), H) as s:
                print("listening on 8080", flush=True); s.serve_forever()
          ports: [{ containerPort: 8080 }]
          resources:
            requests: { cpu: 50m, memory: 128Mi }
            limits:   { cpu: 500m, memory: 256Mi }
          readinessProbe:
            httpGet: { path: /, port: 8080 }
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: apps/v1
kind: Deployment
metadata: { name: portfolio-web, namespace: demo, labels: { app: portfolio-web } }
spec:
  replicas: 2
  selector: { matchLabels: { app: portfolio-web } }
  template:
    metadata: { labels: { app: portfolio-web } }
    spec:
      containers:
        - name: app
          image: python:3.12-slim
          command: ["python","-c"]
          args:
            - |
              import http.server, socketserver
              ballast = bytearray(80 * 1024 * 1024)
              print(f"portfolio-web booting; ballast={len(ballast)//1024//1024}MB", flush=True)
              class H(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                  self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
                def log_message(self,*a): pass
              with socketserver.TCPServer(("",8080), H) as s:
                print("listening on 8080", flush=True); s.serve_forever()
          ports: [{ containerPort: 8080 }]
          resources:
            requests: { cpu: 50m, memory: 128Mi }
            limits:   { cpu: 500m, memory: 256Mi }
          readinessProbe:
            httpGet: { path: /, port: 8080 }
            initialDelaySeconds: 5
            periodSeconds: 10
YAML

# Wait until ready
KUBECONFIG=/tmp/sre-demo-kubeconfig kubectl rollout status -n demo deployment/food-orders
KUBECONFIG=/tmp/sre-demo-kubeconfig kubectl rollout status -n demo deployment/portfolio-web
```

The Python ballast (~100MB) makes the pods OOMKill predictably when chaos drops the memory limit.

---

## 11. Sideload Teams app

The Teams app package is at `infra/teams/sre-agent-teams-app.zip`. If you changed the bot ID, regenerate it:

```bash
# Edit infra/teams/manifest.json — set "id" and "bots[0].botId" to your $BOT_APP_ID
cd infra/teams
zip -j sre-agent-teams-app.zip manifest.json color.png outline.png
cd ../..
```

In Microsoft Teams:

1. **Apps** (left rail) → **Manage your apps** → **Upload an app** → **Upload a custom app**
2. Pick `infra/teams/sre-agent-teams-app.zip`
3. **Add** for personal scope
4. DM the bot — say `hi`. You should get a welcome reply.

If Teams says custom-app upload is disabled, your Teams Admin Center → **Teams apps → Setup policies → Global → Upload custom apps = On**.

**Important:** Both `demo@…` and `@…` users (or whoever you want to receive escalations) must DM the bot **at least once**. The bot's `ConversationReferenceStore` persists the references on disk, so this is a one-time step.

---

## 12. Verify everything

```bash
# Backend healthy?
curl -s http://localhost:8000/healthz

# Dashboard reachable?
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3030

# Prometheus scraping?
curl -s http://localhost:9090/api/v1/targets | python3 -c "
import sys,json
for t in json.load(sys.stdin)['data']['activeTargets']:
    print(f\"  {t['labels']['job']:12s} {t['health']}\")"

# Grafana datasources working?
curl -s -u admin:admin http://localhost:3001/api/datasources | python3 -c "
import sys,json
for d in json.load(sys.stdin):
    print(f\"  {d['name']:12s} {d['type']}\")"

# AKS reachable + agent has rights?
KUBECONFIG=infra/k8s/agent-kubeconfig.yaml kubectl get pods -n demo

# Bot endpoint reachable through ngrok?
curl -s https://<your-ngrok-id>.ngrok-free.dev/healthz

# Jira credentials work?
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" "$JIRA_BASE_URL/rest/api/3/myself" | python3 -m json.tool | head -5
```

Open in browser:

- **Dashboard**: http://localhost:3030
- **Grafana**: http://localhost:3001 (admin/admin) → Dashboards → `App: food-orders`
- **Prometheus**: http://localhost:9090 → Status → Targets
- **Qdrant**: http://localhost:6333/dashboard
- **Demo apps**: http://localhost:8081 (portfolio), http://localhost:8082 (food-orders)

---

## 13. Demo flow

1. **Open** http://localhost:3030/chaos
2. **In the red "Real cluster chaos · LIVE AKS" panel**: pick `food-orders`, click **OOM (8Mi)**
3. The agent will, within ~30-40 seconds:
   - Patch the AKS deployment for real (you can verify with `kubectl get pods -n demo` — pods will be in `CrashLoopBackOff` with restart_count climbing and reason `OOMKilled`)
   - Detect the incident, triage it (P3 by default for tier-1)
   - Gather evidence (Prometheus + Loki + AKS pods + recent deployments)
   - Generate an RCA via OpenRouter (Sonnet 4.5)
   - Propose a fix (`patch_memory_limit` to a higher value)
   - Create a real **Jira ticket** in your `SCRUM` project (you'll get a Teams DM with the link)
   - Send a **Microsoft Teams approval card** to your DM
4. **Click Approve** in Teams → agent runs `kubectl patch` against AKS → memory limit restored → pods recover → verify confirms baseline → Jira ticket gets a comment
5. To reset: click **Restore** in the chaos panel (resets memory + cpu + replicas to healthy defaults)

You'll see the full pipeline in:
- **Cockpit** ([http://localhost:3030](http://localhost:3030)) → Live agent commentary ticker
- **Command Center** ([http://localhost:3030/incidents/INC-…](http://localhost:3030/incidents)) → workflow timeline + embedded Grafana panel + AI insights + raw logs
- **Teams chat** → ticket message + approval card
- **Jira** → ticket SCRUM-N
- **AKS** → real pod restarts via `kubectl get pods -n demo -w`

---

## 14. Troubleshooting

### "agent reads 0 pods / 0 logs / 0 metrics"
- Check `TARGET_NAMESPACE=demo` in `.env` (matches the AKS namespace where pods live)
- Check `KUBECONFIG=/app/kubeconfig.yaml` set in agent container env (`docker exec sre-chatbot-agent-1 env | grep KUBE`)
- Check the SA token kubeconfig was generated correctly (§6.5)

### "Teams bot didn't reply"
- Check `MICROSOFT_APP_*` env vars set in agent container
- Check the Service Principal exists: `az ad sp show --id $BOT_APP_ID`
- Check ngrok is running and the Bot Service `endpoint` matches: `az bot show -g sre-agent-demo -n sre-agent-bot-$USER --query "properties.endpoint"`
- `docker logs sre-chatbot-agent-1 -f` while messaging the bot — look for `/api/messages` POST and any traceback

### "no Jira ticket created"
- Check Jira creds work: `curl -u $JIRA_EMAIL:$JIRA_API_TOKEN $JIRA_BASE_URL/rest/api/3/myself`
- Check the project's `jira_project_key` is set in DB:
  ```bash
  docker exec sre-chatbot-postgres-1 psql -U sre -d sre_agent -c "SELECT id, jira_project_key FROM projects;"
  ```

### "approval card / status DM goes to nobody"
- Both target users must have DM'd the bot at least once. Have them send `hi`.
- Refs are persisted at `/app/data/conversation_refs.json` inside the agent container. If empty, that's why.

### "Grafana panels say No data"
- Set the time range to **Last 15 minutes** (top-right)
- Check Prometheus targets all `up`: http://localhost:9090/targets
- For AKS pod metrics specifically: we don't currently scrape them. Only the local Docker demo apps are scraped. To add AKS scraping, deploy `kube-prometheus-stack` Helm chart and configure remote_write or extend `infra/helm/platform/prometheus-dev.yml`.

### "CPU goes to 700%+ and agent freezes"
- Caused by Insights Monitor + multiple stale incidents looping. Resolve all incidents:
  ```bash
  curl -X POST http://localhost:8000/incidents/_admin/resolve-all
  ```
  Then `docker compose restart agent`.

### "ngrok URL changed, bot stopped working"
- Free ngrok gives you a new URL each restart unless you have a reserved domain. Update Bot Service:
  ```bash
  az bot update -g sre-agent-demo -n sre-agent-bot-$USER \
    --endpoint "https://<new-id>.ngrok-free.dev/api/messages"
  ```

### "Docker stopped / agent container won't start"
- `docker info` should respond. If not, open Docker Desktop and wait for the daemon.
- `docker compose -f docker-compose.dev.yml up -d --force-recreate agent` to recreate just the agent.

---

## What's where in the repo

```
SRE-chatbot/
├── docker-compose.dev.yml       # 12-service local stack
├── .env                         # secrets (git-ignored)
├── SETUP.md                     # ← you're here
├── services/
│   ├── agent/                   # FastAPI + LangGraph
│   ├── dashboard/               # Next.js UI
│   ├── demo-app/                # Flask portfolio + food apps
│   └── chaos-ui/                # legacy Streamlit panel
├── infra/
│   ├── k8s/agent-kubeconfig.yaml      # generated in §6.5
│   ├── teams/sre-agent-teams-app.zip  # Teams sideload package
│   ├── grafana/provisioning/          # Loki + Prometheus datasources
│   ├── promtail/config.yaml           # docker log scraping
│   └── helm/platform/prometheus-dev.yml
├── knowledge_base/
│   ├── runbooks/                # markdown runbooks (RAG)
│   ├── policies/                # markdown policies (RAG)
│   ├── services/                # YAML service catalog (escalation owners)
│   ├── recommended_stacks/      # markdown advisor templates
│   └── history/                 # past incident postmortems
└── scripts/
    └── seed_knowledge_base.py   # loads knowledge_base/* into Qdrant
```

---

**That's it.** You should now have a fully working SRE Agent demo with real cluster integration, real Jira, and real Teams bot. Push some chaos and watch it do its job.
