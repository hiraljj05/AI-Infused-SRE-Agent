from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from pydantic import BaseModel

from sre_agent.application.use_cases.onboard_app import OnboardAppCommand
from sre_agent.domain.entities.app import App, AppId, AppOwner
from sre_agent.domain.entities.project import ProjectId
from sre_agent.domain.entities.service import ServiceTier
from sre_agent.domain.exceptions import DomainError
from sre_agent.domain.value_objects import ServiceName
from sre_agent.interface.rest.dependencies import get_container
from sre_agent.interface.rest.schemas.registry import AppIn, AppView

router = APIRouter(prefix="/api/apps", tags=["apps"])


@router.get("", response_model=list[AppView])
async def list_apps(
    project_id: str | None = None,
    namespace: str | None = None,
    container=Depends(get_container),
) -> list[AppView]:
    async with container.uow_factory() as uow:
        if project_id is not None:
            items = await uow.apps.list_by_project(ProjectId(value=project_id))
        elif namespace is not None:
            items = await uow.apps.list_by_namespace(namespace)
        else:
            items = await uow.apps.list_all()
    return [AppView.from_domain(a) for a in items]


@router.post("", response_model=AppView, status_code=201)
async def create_app(body: AppIn, container=Depends(get_container)) -> AppView:
    async with container.uow_factory() as uow:
        project = await uow.projects.get(ProjectId(value=body.project_id))
        if project is None:
            raise HTTPException(400, f"project {body.project_id} does not exist")
        existing = await uow.apps.get_by_name(ServiceName(body.name))
        if existing is not None:
            raise HTTPException(409, f"app with name {body.name!r} already exists")
        app = App(
            id=AppId.new(),
            project_id=project.id,
            name=ServiceName(body.name),
            namespace=body.namespace,
            tier=ServiceTier(body.tier),
            owners=tuple(AppOwner(email=str(o.email), role=o.role) for o in body.owners),
            runbook_template_id=body.runbook_template_id,
        )
        await uow.apps.add(app)
        await uow.commit()
    return AppView.from_domain(app)


@router.get("/{app_id}", response_model=AppView)
async def get_app(app_id: str, container=Depends(get_container)) -> AppView:
    async with container.uow_factory() as uow:
        a = await uow.apps.get(AppId(value=app_id))
    if a is None:
        raise HTTPException(404, f"app {app_id} not found")
    return AppView.from_domain(a)


@router.put("/{app_id}", response_model=AppView)
async def update_app(
    app_id: str, body: AppIn, container=Depends(get_container)
) -> AppView:
    async with container.uow_factory() as uow:
        a = await uow.apps.get(AppId(value=app_id))
        if a is None:
            raise HTTPException(404, f"app {app_id} not found")
        project = await uow.projects.get(ProjectId(value=body.project_id))
        if project is None:
            raise HTTPException(400, f"project {body.project_id} does not exist")
        updated = App(
            id=a.id,
            project_id=project.id,
            name=ServiceName(body.name),
            namespace=body.namespace,
            tier=ServiceTier(body.tier),
            owners=tuple(AppOwner(email=str(o.email), role=o.role) for o in body.owners),
            runbook_template_id=body.runbook_template_id,
            grafana_dashboard_uid=a.grafana_dashboard_uid,
            enabled=a.enabled,
            created_at=a.created_at,
            metadata=a.metadata,
        )
        await uow.apps.save(updated)
        await uow.commit()
    return AppView.from_domain(updated)


class OnboardAppOut(BaseModel):
    app: AppView
    grafana_dashboard_uid: str | None
    runbook_doc_id: str | None
    warnings: list[str]


@router.post("/onboard", response_model=OnboardAppOut, status_code=201)
async def onboard_app(body: AppIn, container=Depends(get_container)) -> OnboardAppOut:
    """One-click onboarding: persists app + provisions Grafana dashboard + seeds runbook stub."""
    try:
        result = await container.onboard_app_uc.execute(
            OnboardAppCommand(
                project_id=body.project_id,
                name=body.name,
                namespace=body.namespace,
                tier=body.tier,
                owners=[(str(o.email), o.role) for o in body.owners],
                runbook_template_id=body.runbook_template_id,
            )
        )
    except DomainError as exc:
        raise HTTPException(409, str(exc)) from exc
    return OnboardAppOut(
        app=AppView.from_domain(result.app),
        grafana_dashboard_uid=result.grafana_dashboard_uid,
        runbook_doc_id=result.runbook_doc_id,
        warnings=result.warnings,
    )


@router.delete("/{app_id}", status_code=204, response_class=Response)
async def delete_app(app_id: str, container=Depends(get_container)) -> Response:
    async with container.uow_factory() as uow:
        a = await uow.apps.get(AppId(value=app_id))
        if a is None:
            raise HTTPException(404, f"app {app_id} not found")
        await uow.apps.delete(a.id)
        await uow.commit()
    return Response(status_code=204)
