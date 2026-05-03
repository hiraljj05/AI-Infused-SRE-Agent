from __future__ import annotations

from pydantic import BaseModel, Field


class DetectSignalIn(BaseModel):
    service: str = Field(..., min_length=2, max_length=64)
    initial_signal: str = Field(..., min_length=3, max_length=500)
    signal_sources: list[str] = Field(default_factory=list, max_length=20)
    namespace: str | None = None


class DetectSignalOut(BaseModel):
    incident_id: str
    status: str
    started_agent_run: bool
