from __future__ import annotations

import asyncio
from dataclasses import dataclass

import structlog

from sre_agent.domain.entities.incident import Incident
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.ports.notification import StatusNotificationPort
from sre_agent.domain.ports.repositories import UnitOfWork
from sre_agent.domain.ports.ticketing import (
    CreatedTicket,
    EmailMessage,
    EmailPort,
    TicketDraft,
    TicketingPort,
)
from sre_agent.domain.value_objects import IncidentId

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateIncidentTicketCommand:
    incident_id: IncidentId


@dataclass(slots=True, kw_only=True)
class CreateIncidentTicketResult:
    ticket: CreatedTicket | None
    email_sent: bool
    teams_posted: bool
    project_key: str | None
    warnings: list[str]


class CreateIncidentTicketUseCase:
    """Project-aware multi-channel fan-out for a freshly detected incident.

    Looks up the App by service name, then the Project, then dispatches:
      1. Jira ticket (with auto-ack comment)
      2. Email to the project's distribution list
      3. Teams card to the project's channel
    All best-effort; warnings collected, never raises on channel failure.
    """

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        ticketing: TicketingPort,
        email: EmailPort,
        status_notifier: StatusNotificationPort,
    ) -> None:
        self._uow = uow
        self._ticketing = ticketing
        self._email = email
        self._status = status_notifier

    async def execute(self, command: CreateIncidentTicketCommand) -> CreateIncidentTicketResult:
        warnings: list[str] = []

        async with self._uow as uow:
            incident = await uow.incidents.get(command.incident_id)
            if incident is None:
                raise IncidentStateError(f"Incident {command.incident_id} not found")
            app = await uow.apps.get_by_name(incident.service)
            project = (
                await uow.projects.get(app.project_id) if app is not None else None
            )

        if project is None:
            warnings.append(
                f"No project registered for service {incident.service!r}; using defaults"
            )
            project_key = "OPS"
            teams_channel: str | None = None
            email_dist: str | None = None
        else:
            project_key = project.jira_project_key or project.key
            teams_channel = project.teams_channel_id
            email_dist = project.email_distribution

        priority = incident.severity.value if incident.severity else "P3"
        title = self._build_title(incident, priority)
        description = self._build_description(incident, app, project)

        # Fan out in parallel
        ticket_task = self._create_ticket_safe(project_key, title, description, priority, incident)
        email_task = self._send_email_safe(email_dist, title, description, project_key)
        teams_task = self._post_teams_safe(teams_channel, incident, title)

        ticket_result, email_ok, teams_ok = await asyncio.gather(
            ticket_task, email_task, teams_task
        )

        if not email_ok:
            warnings.append("Email delivery failed (see logs)")
        if not teams_ok:
            warnings.append("Teams post failed (see logs)")

        # Auto-ack on the ticket if it was created
        if ticket_result is not None:
            # Persist ticket info on the incident so the API + UI + cards can
            # surface the link. Do this BEFORE auto-ack so a slow Jira
            # comment call doesn't delay the dashboard update.
            try:
                async with self._uow as uow:
                    fresh = await uow.incidents.get(command.incident_id)
                    if fresh is not None:
                        fresh.attach_ticket(
                            key=ticket_result.key, url=ticket_result.url
                        )
                        await uow.incidents.save(fresh)
                        await uow.commit()
            except Exception as exc:
                warnings.append(f"persist ticket on incident failed: {exc}")
                log.exception("attach_ticket persist failed")

            try:
                await self._ticketing.add_comment(
                    ticket_result.key,
                    "Agent acknowledged automatically. RCA in progress.",
                )
            except Exception as exc:
                warnings.append(f"Auto-ack on Jira failed: {exc}")

            # Also surface the Jira link to the user's Teams DM so they see it
            # immediately (not only at approval time).
            try:
                await self._status.post_incident_update(
                    incident=incident,
                    summary=(
                        f"🎫 Jira ticket created: [{ticket_result.key}]({ticket_result.url}) — "
                        f"priority {priority}, project {project_key}. "
                        "Agent is gathering evidence now; approval card will follow."
                    ),
                )
            except Exception:
                log.exception("status post for ticket link failed")

        return CreateIncidentTicketResult(
            ticket=ticket_result,
            email_sent=email_ok,
            teams_posted=teams_ok,
            project_key=project_key,
            warnings=warnings,
        )

    @staticmethod
    def _build_title(incident: Incident, priority: str) -> str:
        return f"[{priority}] {incident.service} - {incident.initial_signal}"

    @staticmethod
    def _build_description(incident: Incident, app: object | None, project: object | None) -> str:
        lines = [
            f"Incident ID: {incident.id}",
            f"Service: {incident.service}",
            f"Severity: {incident.severity.value if incident.severity else 'pending'}",
            f"Detected at: {incident.detected_at.isoformat()}",
            f"Signal: {incident.initial_signal}",
            f"Sources: {', '.join(incident.signal_sources) or 'n/a'}",
        ]
        if incident.blast_radius:
            lines.append(f"Blast radius: {incident.blast_radius.human_readable}")
        if app is not None:
            lines.append(f"App: {getattr(app, 'name', 'n/a')} (tier {getattr(app, 'tier', 'n/a')})")
        if project is not None:
            lines.append(f"Project: {getattr(project, 'name', 'n/a')}")
        return "\n".join(lines)

    async def _create_ticket_safe(
        self,
        project_key: str,
        title: str,
        description: str,
        priority: str,
        incident: Incident,
    ) -> CreatedTicket | None:
        try:
            return await self._ticketing.create_ticket(
                TicketDraft(
                    project_key=project_key,
                    summary=title,
                    description=description,
                    priority=priority,
                    labels=("sre-agent", str(incident.service), priority.lower()),
                )
            )
        except Exception as exc:
            log.exception("ticket creation failed", project_key=project_key)
            return None

    async def _send_email_safe(
        self, email_dist: str | None, title: str, description: str, project_key: str
    ) -> bool:
        if not email_dist:
            return False
        try:
            await self._email.send(
                EmailMessage(
                    to=[email_dist],
                    subject=f"[{project_key}] {title}",
                    body_text=description,
                )
            )
            return True
        except Exception:
            log.exception("email send failed", to=email_dist)
            return False

    async def _post_teams_safe(
        self, channel_id: str | None, incident: Incident, title: str
    ) -> bool:
        try:
            await self._status.post_incident_update(
                incident=incident,
                summary=title,
                channel_id=channel_id,
            )
            return True
        except Exception:
            log.exception("teams post failed", channel_id=channel_id)
            return False
