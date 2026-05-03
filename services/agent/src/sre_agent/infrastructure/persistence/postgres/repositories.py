from __future__ import annotations

from dataclasses import asdict, is_dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sre_agent.domain.entities.approval import Approval, ApprovalSagaState
from sre_agent.domain.entities.incident import Incident, IncidentStatus
from sre_agent.domain.entities.postmortem import Postmortem
from sre_agent.domain.events.base import DomainEvent
from sre_agent.domain.ports.repositories import (
    ApprovalRepository,
    EventStore,
    IncidentRepository,
    PostmortemRepository,
)
from sre_agent.domain.value_objects import ApprovalId, IncidentId, ServiceName
from sre_agent.infrastructure.persistence.models.orm import (
    ApprovalModel,
    EventModel,
    IncidentModel,
    PostmortemModel,
)
from sre_agent.infrastructure.persistence.postgres.mappers import (
    apply_approval_to_model,
    apply_incident_to_model,
    approval_from_model,
    approval_to_model,
    incident_from_model,
    incident_to_model,
    postmortem_from_model,
    postmortem_to_model,
)


class SqlAlchemyIncidentRepository(IncidentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, incident: Incident) -> None:
        self._s.add(incident_to_model(incident))

    async def get(self, incident_id: IncidentId) -> Incident | None:
        model = await self._s.get(IncidentModel, incident_id.value)
        return incident_from_model(model) if model else None

    async def save(self, incident: Incident) -> None:
        model = await self._s.get(IncidentModel, incident.id.value)
        if model is None:
            self._s.add(incident_to_model(incident))
        else:
            apply_incident_to_model(incident, model)

    async def list_active(self) -> list[Incident]:
        active_statuses = [
            s.value for s in IncidentStatus if s not in (IncidentStatus.RESOLVED, IncidentStatus.FAILED)
        ]
        stmt = select(IncidentModel).where(IncidentModel.status.in_(active_statuses))
        result = await self._s.execute(stmt)
        return [incident_from_model(m) for m in result.scalars().all()]

    async def list_recent(self, *, limit: int = 200) -> list[Incident]:
        stmt = (
            select(IncidentModel)
            .order_by(IncidentModel.detected_at.desc())
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return [incident_from_model(m) for m in result.scalars().all()]

    async def list_for_service(
        self, service: ServiceName, *, limit: int = 50
    ) -> list[Incident]:
        stmt = (
            select(IncidentModel)
            .where(IncidentModel.service == str(service))
            .order_by(IncidentModel.detected_at.desc())
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return [incident_from_model(m) for m in result.scalars().all()]

    async def find_active_for_service(self, service: ServiceName) -> Incident | None:
        active_statuses = [
            s.value for s in IncidentStatus if s not in (IncidentStatus.RESOLVED, IncidentStatus.FAILED)
        ]
        stmt = (
            select(IncidentModel)
            .where(
                IncidentModel.service == str(service),
                IncidentModel.status.in_(active_statuses),
            )
            .order_by(IncidentModel.detected_at.desc())
            .limit(1)
        )
        result = await self._s.execute(stmt)
        model = result.scalar_one_or_none()
        return incident_from_model(model) if model else None

    async def list_by_status(self, status: IncidentStatus) -> list[Incident]:
        stmt = select(IncidentModel).where(IncidentModel.status == status.value)
        result = await self._s.execute(stmt)
        return [incident_from_model(m) for m in result.scalars().all()]

    async def list_with_pollable_jira_tickets(self) -> list[Incident]:
        terminal_jira_statuses = ("Done", "Closed", "Resolved", "Cancelled", "Won't Do")
        stmt = select(IncidentModel).where(
            IncidentModel.jira_ticket_key.is_not(None),
            (
                IncidentModel.jira_ticket_status.is_(None)
                | IncidentModel.jira_ticket_status.notin_(terminal_jira_statuses)
            ),
        )
        result = await self._s.execute(stmt)
        return [incident_from_model(m) for m in result.scalars().all()]


class SqlAlchemyApprovalRepository(ApprovalRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, approval: Approval) -> None:
        self._s.add(approval_to_model(approval))

    async def get(self, approval_id: ApprovalId) -> Approval | None:
        model = await self._s.get(ApprovalModel, approval_id.value)
        return approval_from_model(model) if model else None

    async def save(self, approval: Approval) -> None:
        model = await self._s.get(ApprovalModel, approval.id.value)
        if model is None:
            self._s.add(approval_to_model(approval))
        else:
            apply_approval_to_model(approval, model)

    async def get_for_incident(self, incident_id: IncidentId) -> Approval | None:
        stmt = (
            select(ApprovalModel)
            .where(ApprovalModel.incident_id == incident_id.value)
            .order_by(ApprovalModel.requested_at.desc())
            .limit(1)
        )
        result = await self._s.execute(stmt)
        model = result.scalar_one_or_none()
        return approval_from_model(model) if model else None

    async def list_open(self) -> list[Approval]:
        open_states = [
            ApprovalSagaState.NOTIFIED_PRIMARY.value,
            ApprovalSagaState.NOTIFIED_SECONDARY.value,
            ApprovalSagaState.ESCALATED_TO_COMMANDER.value,
        ]
        stmt = select(ApprovalModel).where(ApprovalModel.state.in_(open_states))
        result = await self._s.execute(stmt)
        return [approval_from_model(m) for m in result.scalars().all()]


class SqlAlchemyPostmortemRepository(PostmortemRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, postmortem: Postmortem) -> None:
        self._s.add(postmortem_to_model(postmortem))

    async def get(self, postmortem_id: str) -> Postmortem | None:
        model = await self._s.get(PostmortemModel, postmortem_id)
        return postmortem_from_model(model) if model else None

    async def save(self, postmortem: Postmortem) -> None:
        # Postmortems are append-only in practice; replace if exists.
        model = await self._s.get(PostmortemModel, postmortem.id)
        if model is None:
            self._s.add(postmortem_to_model(postmortem))
        else:
            new = postmortem_to_model(postmortem)
            model.title = new.title
            model.summary = new.summary
            model.root_cause = new.root_cause
            model.impact = new.impact
            model.lessons_learned = new.lessons_learned
            model.timeline = new.timeline
            model.corrective_actions = new.corrective_actions
            model.published_at = new.published_at
            model.signed_off_by = new.signed_off_by

    async def get_for_incident(self, incident_id: IncidentId) -> Postmortem | None:
        stmt = (
            select(PostmortemModel)
            .where(PostmortemModel.incident_id == incident_id.value)
            .order_by(PostmortemModel.drafted_at.desc())
            .limit(1)
        )
        result = await self._s.execute(stmt)
        model = result.scalar_one_or_none()
        return postmortem_from_model(model) if model else None

    async def list_recent(self, *, limit: int = 100) -> list[Postmortem]:
        stmt = (
            select(PostmortemModel)
            .order_by(PostmortemModel.drafted_at.desc())
            .limit(limit)
        )
        result = await self._s.execute(stmt)
        return [postmortem_from_model(m) for m in result.scalars().all()]


class SqlAlchemyEventStore(EventStore):
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def append(self, events: list[DomainEvent]) -> None:
        if events:
            # Ensure any parent Incident inserted in this session is written before event FK is checked.
            await self._s.flush()
        for event in events:
            raw_incident_id = getattr(event, "incident_id", None)
            if raw_incident_id is None:
                continue
            fk_value = (
                raw_incident_id.value
                if isinstance(raw_incident_id, IncidentId)
                else str(raw_incident_id)
            )
            payload = _event_payload(event)
            payload.pop("incident_id", None)
            self._s.add(
                EventModel(
                    event_id=event.event_id,
                    incident_id=fk_value,
                    event_type=event.event_type,
                    version=event.version,
                    occurred_at=event.occurred_at,
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    caused_by=event.caused_by,
                    payload=payload,
                )
            )

    async def load_for_incident(self, incident_id: IncidentId) -> list[DomainEvent]:
        _ = incident_id  # reconstituting typed events is handled by a separate replayer
        return []


def _event_payload(event: DomainEvent) -> dict:
    if is_dataclass(event):
        raw = asdict(event)
    else:
        raw = {k: getattr(event, k) for k in vars(event)}

    return {k: _jsonify(v) for k, v in raw.items() if k not in {"event_id", "occurred_at", "correlation_id", "causation_id", "caused_by"}}


def _jsonify(value: object) -> object:
    from datetime import datetime
    from enum import Enum

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value") and not isinstance(value, dict):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if is_dataclass(value):
        return {k: _jsonify(v) for k, v in asdict(value).items()}
    return value
