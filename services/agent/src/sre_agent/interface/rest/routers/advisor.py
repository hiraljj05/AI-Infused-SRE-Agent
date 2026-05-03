from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from sre_agent.application.use_cases.run_advisory_conversation import AdvisoryProfile
from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


class AdvisorRequest(BaseModel):
    cloud: Literal["azure", "aws", "gcp", "on-prem", "multi"]
    workload_type: Literal["web", "api", "batch", "ml", "data-pipeline", "iot", "other"]
    scale: Literal["startup", "growth", "enterprise"]
    compliance: list[str] = Field(default_factory=list, max_length=10)
    latency_target_ms: int = Field(default=200, ge=1, le=60000)
    extra_context: str = Field(default="", max_length=2000)


class AdvisorResponse(BaseModel):
    recommendation_markdown: str
    cited_docs: list[str]
    model: str


@router.post("", response_model=AdvisorResponse)
async def advise(body: AdvisorRequest, container=Depends(get_container)) -> AdvisorResponse:
    profile = AdvisoryProfile(
        cloud=body.cloud,
        workload_type=body.workload_type,
        scale=body.scale,
        compliance=body.compliance,
        latency_target_ms=body.latency_target_ms,
        extra_context=body.extra_context,
    )
    result = await container.advisor_uc.execute(profile)
    return AdvisorResponse(
        recommendation_markdown=result.recommendation_markdown,
        cited_docs=result.cited_docs,
        model=result.model,
    )
