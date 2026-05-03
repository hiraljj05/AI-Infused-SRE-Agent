from __future__ import annotations

from dataclasses import dataclass

import structlog

from sre_agent.domain.entities.app import App, AppId, AppOwner
from sre_agent.domain.entities.project import ProjectId
from sre_agent.domain.entities.service import ServiceTier
from sre_agent.domain.exceptions import DomainError
from sre_agent.domain.ports.knowledge import KnowledgeDocument, KnowledgePort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import ServiceName

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class OnboardAppCommand:
    project_id: str
    name: str
    namespace: str
    tier: str
    owners: list[tuple[str, str]]  # [(email, role)]
    runbook_template_id: str = "default-web-service"


@dataclass(slots=True, kw_only=True)
class OnboardAppResult:
    app: App
    grafana_dashboard_uid: str | None
    runbook_doc_id: str | None
    warnings: list[str]


_DEFAULT_RUNBOOK_BODY = """## Symptoms
(Replace this with the typical failure modes for {app})

## Diagnosis
1. Check {app} pod status: `kubectl -n {ns} get pods -l app={app}`
2. Inspect recent logs for errors: `kubectl -n {ns} logs -l app={app} --tail=200`
3. Check upstream/downstream dependencies

## Remediation paths
- Transient: `restart_pod` to clear in-pod state
- Resource pressure: `scale_deployment` (HIL required) or increase memory limit (HIL)
- Recent deploy regression: `rollback_deployment` (HIL required)
"""


class OnboardAppUseCase:
    """Persists a new App and bootstraps its observability + runbook stub.

    Steps:
      1. Validate project exists and app name is free
      2. Persist the App
      3. Generate a Grafana dashboard from the template (best-effort)
      4. Seed a runbook stub in the knowledge base (best-effort)
      5. Return result with warnings for any best-effort steps that failed
    """

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        knowledge: KnowledgePort,
        grafana: object | None = None,
    ) -> None:
        self._uow = uow
        self._knowledge = knowledge
        self._grafana = grafana

    async def execute(self, command: OnboardAppCommand) -> OnboardAppResult:
        warnings: list[str] = []

        async with self._uow as uow:
            project = await uow.projects.get(ProjectId(value=command.project_id))
            if project is None:
                raise DomainError(f"project {command.project_id} not found")

            existing = await uow.apps.get_by_name(ServiceName(command.name))
            if existing is not None:
                raise DomainError(f"app {command.name!r} already registered")

            app = App(
                id=AppId.new(),
                project_id=project.id,
                name=ServiceName(command.name),
                namespace=command.namespace,
                tier=ServiceTier(command.tier),
                owners=tuple(
                    AppOwner(email=email, role=role) for email, role in command.owners
                ),
                runbook_template_id=command.runbook_template_id,
            )
            await uow.apps.add(app)
            await uow.commit()

        # Best-effort: Grafana dashboard
        grafana_uid: str | None = None
        if self._grafana is not None:
            try:
                from sre_agent.infrastructure.grafana.grafana_adapter import (
                    build_app_dashboard_template,
                )

                dashboard = build_app_dashboard_template(
                    app_name=command.name, namespace=command.namespace
                )
                grafana_uid = await self._grafana.upsert_dashboard(dashboard)  # type: ignore[attr-defined]
                # Persist the UID back on the app
                async with self._uow as uow:
                    saved = await uow.apps.get(app.id)
                    if saved is not None:
                        saved.grafana_dashboard_uid = grafana_uid
                        await uow.apps.save(saved)
                        await uow.commit()
                        app = saved
            except Exception as exc:
                log.warning("grafana dashboard generation failed", error=str(exc))
                warnings.append(f"Grafana dashboard generation failed: {exc}")

        # Best-effort: KB runbook stub
        runbook_doc_id: str | None = None
        try:
            doc = KnowledgeDocument(
                id=f"RB-{command.name.upper()}-STUB",
                kind="runbook",
                title=f"{command.name} - default runbook (auto-generated)",
                content=_DEFAULT_RUNBOOK_BODY.format(app=command.name, ns=command.namespace),
                metadata={"service": command.name, "auto_generated": "true"},
            )
            await self._knowledge.upsert([doc])
            runbook_doc_id = doc.id
        except Exception as exc:
            log.warning("runbook stub creation failed", error=str(exc))
            warnings.append(f"Runbook stub creation failed: {exc}")

        return OnboardAppResult(
            app=app,
            grafana_dashboard_uid=grafana_uid,
            runbook_doc_id=runbook_doc_id,
            warnings=warnings,
        )
