from __future__ import annotations

from typing import Protocol

from sre_agent.domain.entities.approval import Approval
from sre_agent.domain.entities.incident import Incident, IncidentStatus
from sre_agent.domain.entities.postmortem import Postmortem
from sre_agent.domain.events.base import DomainEvent
from sre_agent.domain.ports.lessons import LessonsRepository
from sre_agent.domain.ports.registry import AppRepository, ProjectRepository
from sre_agent.domain.ports.sla import SLATrackerRepository
from sre_agent.domain.value_objects import ApprovalId, IncidentId, ServiceName


class IncidentRepository(Protocol):
    async def add(self, incident: Incident) -> None:
        ...

    async def get(self, incident_id: IncidentId) -> Incident | None:
        ...

    async def save(self, incident: Incident) -> None:
        ...

    async def list_active(self) -> list[Incident]:
        ...

    async def list_recent(self, *, limit: int = 200) -> list[Incident]:
        """All incidents (any status) ordered by detected_at desc. Used by the
        dashboard to show full history."""
        ...

    async def list_for_service(
        self, service: ServiceName, *, limit: int = 50
    ) -> list[Incident]:
        ...

    async def find_active_for_service(self, service: ServiceName) -> Incident | None:
        ...

    async def list_by_status(self, status: IncidentStatus) -> list[Incident]:
        ...

    async def list_with_pollable_jira_tickets(self) -> list[Incident]:
        """Incidents that have a Jira key whose ticket is not yet in a terminal
        Jira state (Done / Closed / Resolved). Used by the status poller."""
        ...


class ApprovalRepository(Protocol):
    async def add(self, approval: Approval) -> None:
        ...

    async def get(self, approval_id: ApprovalId) -> Approval | None:
        ...

    async def save(self, approval: Approval) -> None:
        ...

    async def get_for_incident(self, incident_id: IncidentId) -> Approval | None:
        ...


class PostmortemRepository(Protocol):
    async def add(self, postmortem: Postmortem) -> None:
        ...

    async def get(self, postmortem_id: str) -> Postmortem | None:
        ...

    async def save(self, postmortem: Postmortem) -> None:
        ...

    async def get_for_incident(self, incident_id: IncidentId) -> Postmortem | None:
        """Latest postmortem drafted for the given incident, if any."""
        ...

    async def list_recent(self, *, limit: int = 100) -> list[Postmortem]:
        """All postmortems ordered by drafted_at desc."""
        ...


class EventStore(Protocol):
    async def append(self, events: list[DomainEvent]) -> None:
        ...

    async def load_for_incident(self, incident_id: IncidentId) -> list[DomainEvent]:
        ...


class UnitOfWork(Protocol):
    incidents: IncidentRepository
    approvals: ApprovalRepository
    postmortems: PostmortemRepository
    events: EventStore
    projects: ProjectRepository
    apps: AppRepository
    slas: SLATrackerRepository
    lessons: LessonsRepository

    async def __aenter__(self) -> "UnitOfWork":
        ...

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...
