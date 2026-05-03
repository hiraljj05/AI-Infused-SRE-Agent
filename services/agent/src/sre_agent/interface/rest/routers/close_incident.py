from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from sre_agent.application.use_cases.close_incident_with_human_resolution import (
    CloseIncidentCommand,
)
from sre_agent.domain.entities.lesson_learnt import IssueCategory
from sre_agent.domain.exceptions import IncidentStateError
from sre_agent.domain.value_objects import IncidentId
from sre_agent.interface.rest.auth import Identity, require_identity
from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


class CloseIncidentIn(BaseModel):
    actor_email: EmailStr
    issue_category: Literal[
        "connection_pool",
        "oom",
        "latency",
        "deploy_regression",
        "network",
        "upstream_dependency",
        "db_lock",
        "queue_backup",
        "config_error",
        "cert_expiry",
        "crash_loop",
        "other",
    ]
    fix_description: str = Field(..., min_length=10, max_length=1000)
    fix_rationale: str = Field(..., min_length=10, max_length=1000)
    could_agent_handle: Literal["yes", "no", "with_approval"]
    tags: list[str] = Field(default_factory=list, max_length=10)


class CloseIncidentOut(BaseModel):
    lesson_id: str
    incident_id: str
    confidence: float
    human_verified: bool


@router.post("/{incident_id}/close", response_model=CloseIncidentOut)
async def close_incident(
    incident_id: str,
    body: CloseIncidentIn,
    container=Depends(get_container),
    identity: Identity = Depends(require_identity),
) -> CloseIncidentOut:
    actor = (
        identity.email
        if identity.email and identity.email != "anonymous@local"
        else str(body.actor_email)
    )
    try:
        lesson = await container.close_incident_uc.execute(
            CloseIncidentCommand(
                incident_id=IncidentId(value=incident_id),
                actor_email=actor,
                issue_category=IssueCategory(body.issue_category),
                fix_description=body.fix_description,
                fix_rationale=body.fix_rationale,
                could_agent_handle=body.could_agent_handle,
                tags=tuple(body.tags),
            )
        )
    except IncidentStateError as exc:
        raise HTTPException(404, str(exc)) from exc
    return CloseIncidentOut(
        lesson_id=lesson.id.value,
        incident_id=incident_id,
        confidence=lesson.confidence,
        human_verified=lesson.human_verified,
    )
