from __future__ import annotations

import secrets
import structlog

from fastapi import APIRouter, Depends, HTTPException

from sre_agent.domain.entities.incident import IncidentStatus
from sre_agent.domain.value_objects import IncidentId, ServiceName
from sre_agent.interface.rest.dependencies import get_container
from sre_agent.interface.rest.schemas.incidents import IncidentView

log = structlog.get_logger(__name__)


def _category_from_signal(signal: str) -> str:
    s = (signal or "").lower()
    if "oom" in s or "memory" in s or "exit code 137" in s:
        return "oom"
    if "cpu" in s or "throttle" in s or "latency" in s:
        return "latency"
    if "scaled to 0" in s or "all pods gone" in s or "outage" in s:
        return "deploy_regression"
    if "crash" in s:
        return "crash_loop"
    return "other"


async def _record_admin_resolution(
    *,
    session,
    incident_id: str,
    service: str,
    actor: str,
    initial_signal: str,
    detected_at,
) -> None:
    """Insert a lessons_learnt row so the People page tab populates and avoid
    Postgres unique-constraint failures on a second resolve of the same incident."""
    from datetime import UTC, datetime
    from sqlalchemy import text

    minutes = max(
        1, int((datetime.now(UTC) - detected_at).total_seconds() // 60)
    ) if detected_at else 1
    cat = _category_from_signal(initial_signal or "")
    fix_text = "Force-resolved from dashboard; deployment restored to baseline (memory=256Mi, cpu=500m, replicas=2)."
    rationale = "Auto-restore via /incidents/_admin/resolve — overrides agent escalation when human knows the underlying chaos was synthetic."
    lesson_id = "lsn_" + secrets.token_hex(14)

    existing = (
        await session.execute(
            text("SELECT id FROM lessons_learnt WHERE incident_id=:inc LIMIT 1"),
            {"inc": incident_id},
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Update the existing lesson's resolver so the People page reflects the
        # human who force-resolved it (overriding any agent-attributed lesson).
        await session.execute(
            text(
                "UPDATE lessons_learnt SET resolver=:resolver, fix_applied=:fix, "
                " human_verified=TRUE WHERE id=:id"
            ),
            {"resolver": f"user:{actor}", "fix": fix_text, "id": existing},
        )
        return

    await session.execute(
        text(
            "INSERT INTO lessons_learnt "
            "(id, incident_id, app_id, project_id, issue_category, root_cause, fix_applied, "
            " resolver, resolution_minutes, tags, confidence, human_verified, created_at) "
            "VALUES (:id, :inc, NULL, NULL, :cat, :rc, :fix, :resolver, :mins, "
            "        CAST(:tags AS jsonb), 1.0, TRUE, :ts)"
        ),
        {
            "id": lesson_id,
            "inc": incident_id,
            "cat": cat,
            "rc": rationale,
            "fix": fix_text,
            "resolver": f"user:{actor}",
            "mins": minutes,
            "tags": '["force_resolve","admin"]',
            "ts": datetime.now(UTC),
        },
    )

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentView])
async def list_incidents(
    status: str | None = None,
    service: str | None = None,
    active: bool = False,
    limit: int = 200,
    container=Depends(get_container),
) -> list[IncidentView]:
    """List incidents.

    Default behaviour returns the most recent ``limit`` incidents (any status)
    so the dashboard can show full history (Postmortems, RCA, Tickets, the
    Incidents page tabs, etc.). Pass ``?active=true`` to restrict to the
    currently-active subset, ``?status=resolved`` to filter by status, or
    ``?service=foo`` to filter by service.
    """
    async with container.uow_factory() as uow:
        if status is not None:
            try:
                parsed_status = IncidentStatus(status)
            except ValueError as exc:
                raise HTTPException(400, f"invalid status: {status}") from exc
            incidents = await uow.incidents.list_by_status(parsed_status)
        elif service is not None:
            incidents = await uow.incidents.list_for_service(ServiceName(service))
        elif active:
            incidents = await uow.incidents.list_active()
        else:
            incidents = await uow.incidents.list_recent(limit=limit)
    return [IncidentView.from_domain(i) for i in incidents]


@router.get("/{incident_id}", response_model=IncidentView)
async def get_incident(
    incident_id: str,
    container=Depends(get_container),
) -> IncidentView:
    async with container.uow_factory() as uow:
        incident = await uow.incidents.get(IncidentId(value=incident_id))
    if incident is None:
        raise HTTPException(404, f"incident {incident_id} not found")
    return IncidentView.from_domain(incident)


@router.post("/_admin/resolve-all", status_code=200)
async def resolve_all(
    actor: str = "dashboard-admin",
    container=Depends(get_container),
) -> dict[str, int | list[str]]:
    """Demo helper — force-resolves every active incident. Bypasses dedup so the next
    chaos push starts a fresh agent run on the same service name. Also records
    lessons-learnt rows and transitions linked Jira tickets to Done (best-effort)."""
    from datetime import UTC, datetime
    from sqlalchemy import text

    jira_transitions: list[str] = []

    async with container.uow_factory() as uow:
        session = uow._session  # type: ignore[attr-defined]
        rows = (
            await session.execute(
                text(
                    "SELECT id, service, initial_signal, detected_at, jira_ticket_key "
                    "FROM incidents WHERE status NOT IN ('resolved','failed')"
                )
            )
        ).all()

        r1 = await session.execute(
            text(
                "UPDATE incidents SET status='resolved', resolved_at=:t "
                "WHERE status NOT IN ('resolved','failed')"
            ),
            {"t": datetime.now(UTC)},
        )
        r2 = await session.execute(
            text(
                "UPDATE sla_trackers SET status='satisfied', satisfied_at=:t "
                "WHERE status IN ('pending','warned')"
            ),
            {"t": datetime.now(UTC)},
        )
        r3 = await session.execute(
            text(
                "UPDATE approvals SET state='timed_out' "
                "WHERE state IN ('notified_primary','notified_secondary','escalated_to_commander')"
            )
        )

        for row in rows:
            await _record_admin_resolution(
                session=session,
                incident_id=row.id,
                service=row.service,
                actor=actor,
                initial_signal=row.initial_signal or "",
                detected_at=row.detected_at,
            )

        await session.commit()

    if getattr(container, "ticketing", None) is not None:
        for row in rows:
            key = row.jira_ticket_key
            if not key:
                continue
            try:
                await container.ticketing.transition_to_resolved(
                    key, resolution=f"Resolved by {actor} via dashboard resolve-all."
                )
                jira_transitions.append(key)
            except Exception as exc:  # noqa: BLE001
                log.warning("jira transition failed", key=key, exc=str(exc))

    return {
        "incidents_resolved": r1.rowcount or 0,
        "slas_closed": r2.rowcount or 0,
        "approvals_timed_out": r3.rowcount or 0,
        "jira_transitioned": jira_transitions,
    }


@router.post("/_admin/backfill-lessons", status_code=200)
async def backfill_lessons(
    actor: str = "PriyanshTyagi",
    container=Depends(get_container),
) -> dict[str, int]:
    """Walk every already-resolved incident that has no lesson_learnt row yet and
    insert one. Use after enabling lesson recording so the People + Knowledge
    pages reflect historical resolutions."""
    from sqlalchemy import text

    async with container.uow_factory() as uow:
        session = uow._session  # type: ignore[attr-defined]
        rows = (
            await session.execute(
                text(
                    "SELECT i.id, i.service, i.initial_signal, i.detected_at "
                    "FROM incidents i "
                    "LEFT JOIN lessons_learnt l ON l.incident_id = i.id "
                    "WHERE i.status='resolved' AND l.id IS NULL"
                )
            )
        ).all()

        inserted = 0
        for row in rows:
            await _record_admin_resolution(
                session=session,
                incident_id=row.id,
                service=row.service,
                actor=actor,
                initial_signal=row.initial_signal or "",
                detected_at=row.detected_at,
            )
            inserted += 1
        await session.commit()

    return {"backfilled": inserted}


@router.post("/_admin/resolve/{incident_id}", status_code=200)
async def admin_resolve_one(
    incident_id: str,
    actor: str = "dashboard-admin",
    container=Depends(get_container),
) -> dict[str, str]:
    """Force-resolve a single incident (typically an escalated one) without
    going through the postmortem close flow. Also:
      - restores the deployment to baseline so the underlying service comes back
      - transitions the linked Jira ticket to Done (best-effort)
      - records a lesson_learnt so the People tab attributes the resolution
    """
    from datetime import UTC, datetime
    from sqlalchemy import text

    jira_key: str | None = None
    service_name: str = ""
    initial_signal: str = ""
    detected_at = None

    async with container.uow_factory() as uow:
        session = uow._session  # type: ignore[attr-defined]
        incident = await uow.incidents.get(IncidentId(value=incident_id))
        if incident is None:
            raise HTTPException(404, f"incident {incident_id} not found")
        service_name = str(incident.service)
        jira_key = getattr(incident, "jira_ticket_key", None)
        initial_signal = getattr(incident, "initial_signal", "") or ""
        detected_at = getattr(incident, "detected_at", None)

        await session.execute(
            text(
                "UPDATE incidents SET status='resolved', resolved_at=:t "
                "WHERE id=:id AND status NOT IN ('resolved','failed')"
            ),
            {"t": datetime.now(UTC), "id": incident_id},
        )
        await session.execute(
            text(
                "UPDATE sla_trackers SET status='satisfied', satisfied_at=:t "
                "WHERE incident_id=:id AND status IN ('pending','warned')"
            ),
            {"t": datetime.now(UTC), "id": incident_id},
        )
        await session.execute(
            text(
                "UPDATE approvals SET state='timed_out' "
                "WHERE incident_id=:id AND state IN ('notified_primary','notified_secondary','escalated_to_commander')"
            ),
            {"id": incident_id},
        )
        await _record_admin_resolution(
            session=session,
            incident_id=incident_id,
            service=service_name,
            actor=actor,
            initial_signal=initial_signal,
            detected_at=detected_at,
        )
        await session.commit()

    restore_status = "skipped"
    try:
        await container.k8s.patch_resource_limit(
            namespace="demo",
            deployment=service_name,
            container="app",
            resource="memory",
            limit="256Mi",
            reason="admin-resolve restore",
        )
        await container.k8s.patch_resource_limit(
            namespace="demo",
            deployment=service_name,
            container="app",
            resource="cpu",
            limit="500m",
            reason="admin-resolve restore",
        )
        await container.k8s.scale_deployment(
            namespace="demo",
            deployment=service_name,
            replicas=2,
            reason="admin-resolve restore",
        )
        restore_status = "restored"
    except Exception as exc:  # noqa: BLE001
        restore_status = f"restore-failed: {exc!s}"[:200]

    jira_status = "skipped"
    if jira_key and getattr(container, "ticketing", None) is not None:
        try:
            await container.ticketing.transition_to_resolved(
                jira_key, resolution=f"Resolved by {actor} via dashboard force-resolve."
            )
            jira_status = f"transitioned: {jira_key}"
        except Exception as exc:  # noqa: BLE001
            jira_status = f"transition-failed: {exc!s}"[:200]
            log.warning("jira transition failed", key=jira_key, exc=str(exc))

    return {
        "incident_id": incident_id,
        "service": service_name,
        "status": "resolved",
        "deployment_restore": restore_status,
        "jira": jira_status,
        "actor": actor,
    }
