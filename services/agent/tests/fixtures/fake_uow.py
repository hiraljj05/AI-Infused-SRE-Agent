"""In-memory fakes for UnitOfWork / repositories / event store, for unit tests."""
from __future__ import annotations

from types import TracebackType
from typing import Self

from sre_agent.domain.entities.approval import Approval, ApprovalSagaState
from sre_agent.domain.entities.incident import Incident, IncidentStatus
from sre_agent.domain.entities.postmortem import Postmortem
from sre_agent.domain.events.base import DomainEvent
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.value_objects import ApprovalId, IncidentId, ServiceName


class FakeIncidentRepo:
    def __init__(self) -> None:
        self._data: dict[str, Incident] = {}

    async def add(self, incident: Incident) -> None:
        self._data[incident.id.value] = incident

    async def get(self, incident_id: IncidentId) -> Incident | None:
        return self._data.get(incident_id.value)

    async def save(self, incident: Incident) -> None:
        self._data[incident.id.value] = incident

    async def list_active(self) -> list[Incident]:
        return [i for i in self._data.values() if i.is_active]

    async def list_recent(self, *, limit: int = 200) -> list[Incident]:
        items = sorted(
            self._data.values(),
            key=lambda i: i.detected_at,
            reverse=True,
        )
        return items[:limit]

    async def list_for_service(self, service: ServiceName, *, limit: int = 50) -> list[Incident]:
        return [i for i in self._data.values() if str(i.service) == str(service)][:limit]

    async def find_active_for_service(self, service: ServiceName) -> Incident | None:
        for i in self._data.values():
            if str(i.service) == str(service) and i.is_active:
                return i
        return None

    async def list_by_status(self, status: IncidentStatus) -> list[Incident]:
        return [i for i in self._data.values() if i.status == status]


class FakeApprovalRepo:
    def __init__(self) -> None:
        self._data: dict[str, Approval] = {}

    async def add(self, approval: Approval) -> None:
        self._data[approval.id.value] = approval

    async def get(self, approval_id: ApprovalId) -> Approval | None:
        return self._data.get(approval_id.value)

    async def save(self, approval: Approval) -> None:
        self._data[approval.id.value] = approval

    async def get_for_incident(self, incident_id: IncidentId) -> Approval | None:
        for a in self._data.values():
            if a.incident_id == incident_id:
                return a
        return None

    async def list_open(self) -> list[Approval]:
        return [
            a
            for a in self._data.values()
            if a.state
            in (
                ApprovalSagaState.NOTIFIED_PRIMARY,
                ApprovalSagaState.NOTIFIED_SECONDARY,
                ApprovalSagaState.ESCALATED_TO_COMMANDER,
            )
        ]


class FakePostmortemRepo:
    def __init__(self) -> None:
        self._data: dict[str, Postmortem] = {}

    async def add(self, pm: Postmortem) -> None:
        self._data[pm.id] = pm

    async def get(self, postmortem_id: str) -> Postmortem | None:
        return self._data.get(postmortem_id)

    async def save(self, pm: Postmortem) -> None:
        self._data[pm.id] = pm

    async def get_for_incident(self, incident_id: IncidentId) -> Postmortem | None:
        items = [p for p in self._data.values() if p.incident_id == incident_id]
        items.sort(key=lambda p: p.drafted_at, reverse=True)
        return items[0] if items else None

    async def list_recent(self, *, limit: int = 100) -> list[Postmortem]:
        items = sorted(self._data.values(), key=lambda p: p.drafted_at, reverse=True)
        return items[:limit]


class FakeEventStore:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def append(self, events: list[DomainEvent]) -> None:
        self.events.extend(events)

    async def load_for_incident(self, incident_id: IncidentId) -> list[DomainEvent]:
        return [e for e in self.events if getattr(e, "incident_id", None) == incident_id]


class FakeUoW(UnitOfWork):
    def __init__(self) -> None:
        self.incidents = FakeIncidentRepo()
        self.approvals = FakeApprovalRepo()
        self.postmortems = FakePostmortemRepo()
        self.events = FakeEventStore()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
