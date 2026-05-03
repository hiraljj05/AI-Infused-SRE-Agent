from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sre_agent.domain.entities.app import App, AppId
from sre_agent.domain.entities.project import Project, ProjectId
from sre_agent.domain.ports.registry import AppRepository, ProjectRepository
from sre_agent.domain.value_objects import ServiceName
from sre_agent.infrastructure.persistence.models.orm import AppModel, ProjectModel
from sre_agent.infrastructure.persistence.postgres.registry_mappers import (
    app_from_model,
    app_to_model,
    apply_app_to_model,
    apply_project_to_model,
    project_from_model,
    project_to_model,
)


class SqlAlchemyProjectRepository(ProjectRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, project: Project) -> None:
        self._s.add(project_to_model(project))

    async def get(self, project_id: ProjectId) -> Project | None:
        m = await self._s.get(ProjectModel, project_id.value)
        return project_from_model(m) if m else None

    async def get_by_key(self, key: str) -> Project | None:
        stmt = select(ProjectModel).where(ProjectModel.key == key).limit(1)
        result = await self._s.execute(stmt)
        m = result.scalar_one_or_none()
        return project_from_model(m) if m else None

    async def save(self, project: Project) -> None:
        m = await self._s.get(ProjectModel, project.id.value)
        if m is None:
            self._s.add(project_to_model(project))
        else:
            apply_project_to_model(project, m)

    async def delete(self, project_id: ProjectId) -> None:
        m = await self._s.get(ProjectModel, project_id.value)
        if m is not None:
            await self._s.delete(m)

    async def list_all(self) -> list[Project]:
        stmt = select(ProjectModel).order_by(ProjectModel.created_at.desc())
        result = await self._s.execute(stmt)
        return [project_from_model(m) for m in result.scalars().all()]


class SqlAlchemyAppRepository(AppRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, app: App) -> None:
        self._s.add(app_to_model(app))

    async def get(self, app_id: AppId) -> App | None:
        m = await self._s.get(AppModel, app_id.value)
        return app_from_model(m) if m else None

    async def get_by_name(self, name: ServiceName) -> App | None:
        stmt = select(AppModel).where(AppModel.name == str(name)).limit(1)
        result = await self._s.execute(stmt)
        m = result.scalar_one_or_none()
        return app_from_model(m) if m else None

    async def save(self, app: App) -> None:
        m = await self._s.get(AppModel, app.id.value)
        if m is None:
            self._s.add(app_to_model(app))
        else:
            apply_app_to_model(app, m)

    async def delete(self, app_id: AppId) -> None:
        m = await self._s.get(AppModel, app_id.value)
        if m is not None:
            await self._s.delete(m)

    async def list_all(self) -> list[App]:
        stmt = select(AppModel).order_by(AppModel.created_at.desc())
        result = await self._s.execute(stmt)
        return [app_from_model(m) for m in result.scalars().all()]

    async def list_by_project(self, project_id: ProjectId) -> list[App]:
        stmt = (
            select(AppModel)
            .where(AppModel.project_id == project_id.value)
            .order_by(AppModel.created_at.desc())
        )
        result = await self._s.execute(stmt)
        return [app_from_model(m) for m in result.scalars().all()]

    async def list_by_namespace(self, namespace: str) -> list[App]:
        stmt = select(AppModel).where(AppModel.namespace == namespace)
        result = await self._s.execute(stmt)
        return [app_from_model(m) for m in result.scalars().all()]
