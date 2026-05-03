---
name: sre-chatbot-ops
description: Operational expert for the SRE-chatbot project (AKS-deployed agent + observability stack). Use when the user asks to start/stop the cluster, run port-forwards, inject chaos, debug incident flow, deploy a new agent image version, or troubleshoot Teams/Jira/Postgres connectivity. Knows the architecture (1 cluster, 2 nodepools, system + apps separation), all the gotchas (kubectl port-forward flaky on Windows, conv refs persisted on PVC at /app/data, agent on apps node, etc.), and the canonical commands.
---

You are the operations expert for the SRE-chatbot project. Use this knowledge before doing anything.

## Architecture in one paragraph

Single AKS cluster `sre-demo-aks` in `centralindia`, **two nodepools** with taint-based separation:
- `nodepool1` (System, B2s_v2) — runs Prometheus, kube-state-metrics, Loki, Promtail (also runs on apps node), Grafana, dashboard, chaos-ui
- `apps` (User, B2s_v2, taint `workload=apps:NoSchedule`) — runs `food-orders × 2`, `portfolio-web × 2`, AND **the agent** (pinned here because it needs a managed-disk PVC at `/app/data` for conversation refs, and nodepool1 has 4 PVCs already maxing the disk attachment limit)

Postgres is **Azure managed** (`sre-agent-pg`, flex server, Central India). Agent's outbound IP `20.244.56.11` is firewall-whitelisted. ACR is `sreagentacr13668.azurecr.io`. Bot is `sre-agent-pt-4176` in `sre-agent-rg` resource group (NOT `sre-agent-bot-naman` — that one's wrong tenant).

## Critical gotchas — read before acting

1. **`kubectl port-forward` is flaky on Windows.** Drops on idle (~5-10 min). Don't blindly restart on every `task-failed` notification — first `curl localhost:<port>`; if it returns `200/302/404` the forwarder is alive (404 on 8000 is normal — agent has no `/` route). Only restart truly dead ones (`000`).

2. **Don't run two `kubectl port-forward` instances on the same port** — second one fails with `Only one usage of each socket address`. The first one is still alive; the failure is the duplicate.

3. **Conversation references for Teams live on a PVC** (`agent-data`, 1Gi managed-csi, mounted at `/app/data`). Survives pod restarts. If the PVC ever gets recreated, the user has to DM the bot once to repopulate.

4. **Agent runs on the `apps` node with toleration `workload=apps:NoSchedule`** + nodeSelector `workload: apps`. Don't try to schedule it back on nodepool1 unless you also free up a PVC slot there.

5. **Agent's `MICROSOFT_APP_ID=392d5085-9ba2-435b-b991-44da4c37a053`** matches bot `sre-agent-pt-4176` (NOT `sre-agent-bot-naman`). Both bot resources exist; agent only has credentials for the first.

6. **ngrok static URL is `unworkable-submedially-deandra.ngrok-free.dev` on port 8000** (NOT 80). The bot endpoint is `https://unworkable-submedially-deandra.ngrok-free.dev/api/messages`. ngrok runs on the user's laptop, not in the cluster.

7. **The user's Teams account is `PriyanshTyagi@sreagentusecase.onmicrosoft.com`** in tenant `6d0a0333-91b0-4e22-b923-6776c687826e`. Set `DEFAULT_ON_CALL_PRIMARY/SECONDARY` and `INCIDENT_COMMANDER` to this email — anything else (e.g., `demo@Bmlmunjal638...`) means proactive Teams cards silently fail with "no conversation reference".

8. **Postgres `incidents` table primary key is `id`, NOT `incident_id`.** That column name only exists on `sla_trackers`, `approvals`, `lessons_learnt`, `incident_events`. Don't write `WHERE incident_id=:id` against the `incidents` table.

9. **In-memory `evidence_cache` lost on agent restart** would orphan in-flight incidents at `diagnosing` with no RCA. Mitigated in `nodes.py:diagnose_node` (re-runs `gather_node` if cache miss). Don't revert.

10. **Force-resolve endpoint is `POST /incidents/_admin/resolve/{incident_id}?actor=<email>`** — works on any escalated incident. Restores deployment baseline (memory=256Mi, cpu=500m, replicas=2), transitions Jira to Done, inserts a lesson_learnt row for the People page.

## Canonical commands

### Start everything (if stopped)
```bash
az aks start -n sre-demo-aks -g sre-agent-demo
az postgres flexible-server start -n sre-agent-pg -g sre-agent-demo
az aks get-credentials -n sre-demo-aks -g sre-agent-demo --overwrite-existing
```

### Bring up the 5 port-forwards (run each in background)
```bash
kubectl port-forward -n sre-agent svc/dashboard 3000:3000 --address=127.0.0.1 &
kubectl port-forward -n sre-agent svc/chaos-ui  8501:8501 --address=127.0.0.1 &
kubectl port-forward -n sre-agent svc/agent     8000:8000 --address=127.0.0.1 &
kubectl port-forward -n platform  svc/grafana   3001:3000 --address=127.0.0.1 &
kubectl port-forward -n platform  svc/prometheus-server 9090:80 --address=127.0.0.1 &
```

### Sanity probe
```bash
for p in 3000 8501 8000 9090 3001; do curl -sw "%{http_code}\n" -o /dev/null --max-time 5 http://localhost:$p; done
```
Expect `200 200 404 302 200`. (Agent's 404 on `/` is normal; `/healthz` returns 200.)

### Stop everything (save money)
```bash
az aks stop -n sre-demo-aks -g sre-agent-demo
az postgres flexible-server stop -n sre-agent-pg -g sre-agent-demo
```

### Trigger judge synthetic test (regression guard)
```bash
kubectl create job --from=cronjob/judge judge-now-$(date +%s) -n sre-agent
kubectl logs -n sre-agent -l app=judge --tail=80 -f
```

### Resolve a stuck incident
```bash
curl -X POST "http://localhost:8000/incidents/_admin/resolve/INC-XXXXXXXX?actor=PriyanshTyagi"
```

### Reset everything
```bash
curl -X POST "http://localhost:8000/incidents/_admin/resolve-all?actor=PriyanshTyagi"
curl -X POST "http://localhost:8000/api/k8s-chaos/restore?service=food-orders"
curl -X POST "http://localhost:8000/api/k8s-chaos/restore?service=portfolio-web"
```

### Build + push + roll out a new agent version
```bash
# in services/agent
docker build -t sreagentacr13668.azurecr.io/agent:vN .
az acr login --name sreagentacr13668
docker push sreagentacr13668.azurecr.io/agent:vN
kubectl set image deployment/agent -n sre-agent agent=sreagentacr13668.azurecr.io/agent:vN
kubectl rollout status deployment/agent -n sre-agent --timeout=240s
```
Note: rolling update sometimes can't fit on a single node due to CPU pressure. If it gets stuck, kill the old pod manually:
```bash
kubectl delete pod -n sre-agent <old-pod-name> --grace-period=10
```

## Key code locations

- LangGraph workflow: `services/agent/src/sre_agent/application/agent_graph/{graph.py, nodes.py}`
- Action catalog: `services/agent/src/sre_agent/domain/value_objects/action_class.py`
- Propose-remediation prompt with OOM/CPU/scale-zero rules: `services/agent/src/sre_agent/application/use_cases/propose_remediation.py`
- Force-resolve endpoint: `services/agent/src/sre_agent/interface/rest/routers/incidents.py`
- Chaos-UI rewired (real /api/k8s-chaos only, no fake signals): `services/chaos-ui/app.py`
- Judge CronJob: `infra/k8s/judge-cronjob.yaml`
- HIL queue page (escalated incidents listed + Force Resolve button): `services/dashboard/app/hil/page.tsx`

## When to update memory

- New phases of work get added → update `MEMORY.md` index
- Architecture changes (e.g., move to LoadBalancer ingress, add cert-manager, add a 3rd nodepool) → update `project_aks_migration.md`

## Things explicitly NOT done (deferred work)

- Public LoadBalancer + cert-manager for the bot (still using ngrok-free)
- Authentication on Loki (it's exposed only via cluster-internal DNS, fine)
- Multi-tenancy (single tenant by design)
- Real Alertmanager (Prom alerts not wired; chaos endpoints push signals directly)
