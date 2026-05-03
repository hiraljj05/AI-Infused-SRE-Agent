#!/usr/bin/env bash
# Deploys the SRE Agent stack to an AKS cluster.
# Expects: `az login`, `kubectl` configured, and `helm` installed.
set -euo pipefail

: "${AZURE_RESOURCE_GROUP:?set AZURE_RESOURCE_GROUP}"
: "${AKS_CLUSTER_NAME:=sre-demo-aks}"
: "${GHCR_USERNAME:?set GHCR_USERNAME for image pulls}"
: "${GHCR_PAT:?set GHCR_PAT (GitHub Personal Access Token with read:packages)}"
: "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY}"
: "${MICROSOFT_APP_ID:=}"
: "${MICROSOFT_APP_PASSWORD:=}"
: "${MICROSOFT_APP_TENANT_ID:=}"

echo "==> Getting AKS credentials"
az aks get-credentials --resource-group "$AZURE_RESOURCE_GROUP" --name "$AKS_CLUSTER_NAME" --overwrite-existing

echo "==> Installing Chaos Mesh"
helm repo add chaos-mesh https://charts.chaos-mesh.org || true
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock \
  --wait --timeout 10m

echo "==> Installing kube-prometheus-stack (Prometheus + Grafana)"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true
helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.adminPassword=admin \
  --wait --timeout 15m

echo "==> Installing Loki"
helm repo add grafana https://grafana.github.io/helm-charts || true
helm upgrade --install loki grafana/loki \
  --namespace monitoring \
  --set singleBinary.replicas=1 \
  --set deploymentMode=SingleBinary \
  --set loki.auth_enabled=false \
  --wait --timeout 10m || true

echo "==> Installing in-cluster platform (Postgres + Qdrant)"
helm upgrade --install platform infra/helm/platform \
  --namespace sre-agent --create-namespace \
  --wait --timeout 10m

echo "==> Creating image pull secret for ghcr.io"
kubectl create namespace sre-agent --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username="$GHCR_USERNAME" \
  --docker-password="$GHCR_PAT" \
  --namespace sre-agent --dry-run=client -o yaml | kubectl apply -f -

echo "==> Deploying SRE Agent"
helm upgrade --install sre-agent infra/helm/sre-agent \
  --namespace sre-agent \
  --set secrets.openrouterApiKey="$OPENROUTER_API_KEY" \
  --set secrets.microsoftAppId="$MICROSOFT_APP_ID" \
  --set secrets.microsoftAppPassword="$MICROSOFT_APP_PASSWORD" \
  --set secrets.microsoftAppTenantId="$MICROSOFT_APP_TENANT_ID" \
  --wait --timeout 10m

echo "==> Deploying dummy-app"
helm upgrade --install demo infra/helm/dummy-app \
  --namespace demo-store --create-namespace \
  --wait --timeout 10m

echo "==> Deploying chaos-ui"
helm upgrade --install chaos-ui infra/helm/chaos-ui \
  --namespace chaos-ui --create-namespace \
  --wait --timeout 5m

echo "==> Deploying dashboard"
helm upgrade --install dashboard infra/helm/dashboard \
  --namespace sre-agent \
  --wait --timeout 5m

echo "==> Running DB migrations"
kubectl -n sre-agent run migrate --rm -i --restart=Never \
  --image="ghcr.io/sre-agent/agent:latest" \
  --env="POSTGRES_DSN=postgresql+asyncpg://sre:sre@postgres:5432/sre_agent" \
  --command -- alembic upgrade head

echo "==> Seeding knowledge base"
kubectl -n sre-agent run seed --rm -i --restart=Never \
  --image="ghcr.io/sre-agent/agent:latest" \
  --env="QDRANT_URL=http://qdrant:6333" \
  --env="POSTGRES_DSN=postgresql+asyncpg://sre:sre@postgres:5432/sre_agent" \
  --command -- python scripts/seed_knowledge_base.py

echo "==> Done. Check the dashboard at the ingress host."
