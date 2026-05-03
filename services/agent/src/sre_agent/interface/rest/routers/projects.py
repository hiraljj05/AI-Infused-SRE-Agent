from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from sre_agent.domain.entities.project import Project, ProjectId
from sre_agent.interface.rest.dependencies import get_container
from sre_agent.interface.rest.schemas.registry import ProjectIn, ProjectView

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectView])
async def list_projects(container=Depends(get_container)) -> list[ProjectView]:
    async with container.uow_factory() as uow:
        items = await uow.projects.list_all()
    return [ProjectView.from_domain(p) for p in items]


@router.post("", response_model=ProjectView, status_code=201)
async def create_project(body: ProjectIn, container=Depends(get_container)) -> ProjectView:
    async with container.uow_factory() as uow:
        existing = await uow.projects.get_by_key(body.key)
        if existing is not None:
            raise HTTPException(409, f"project with key {body.key!r} already exists")
        project = Project(
            id=ProjectId.new(),
            key=body.key,
            name=body.name,
            description=body.description,
            teams_channel_id=body.teams_channel_id,
            jira_project_key=body.jira_project_key,
            email_distribution=str(body.email_distribution) if body.email_distribution else None,
            incident_commander_group=body.incident_commander_group,
        )
        await uow.projects.add(project)
        await uow.commit()
    return ProjectView.from_domain(project)


@router.get("/{project_id}", response_model=ProjectView)
async def get_project(project_id: str, container=Depends(get_container)) -> ProjectView:
    async with container.uow_factory() as uow:
        p = await uow.projects.get(ProjectId(value=project_id))
    if p is None:
        raise HTTPException(404, f"project {project_id} not found")
    return ProjectView.from_domain(p)


@router.put("/{project_id}", response_model=ProjectView)
async def update_project(
    project_id: str, body: ProjectIn, container=Depends(get_container)
) -> ProjectView:
    async with container.uow_factory() as uow:
        p = await uow.projects.get(ProjectId(value=project_id))
        if p is None:
            raise HTTPException(404, f"project {project_id} not found")
        updated = Project(
            id=p.id,
            key=body.key,
            name=body.name,
            description=body.description,
            teams_channel_id=body.teams_channel_id,
            jira_project_key=body.jira_project_key,
            email_distribution=str(body.email_distribution) if body.email_distribution else None,
            incident_commander_group=body.incident_commander_group,
            created_at=p.created_at,
        )
        await uow.projects.save(updated)
        await uow.commit()
    return ProjectView.from_domain(updated)


@router.delete("/{project_id}", status_code=204, response_class=Response)
async def delete_project(project_id: str, container=Depends(get_container)) -> Response:
    async with container.uow_factory() as uow:
        p = await uow.projects.get(ProjectId(value=project_id))
        if p is None:
            raise HTTPException(404, f"project {project_id} not found")
        await uow.projects.delete(p.id)
        await uow.commit()
    return Response(status_code=204)
