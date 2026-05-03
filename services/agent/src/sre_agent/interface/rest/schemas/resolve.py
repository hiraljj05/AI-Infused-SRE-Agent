from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResolveApprovalIn(BaseModel):
    approval_id: str = Field(..., min_length=5)
    decision: Literal["approve", "reject", "modify"]
    actor: str = Field(..., min_length=2, max_length=128)
    reason: str | None = None
    modifications: str | None = None


class ResolveApprovalOut(BaseModel):
    approval_id: str
    state: str
    finalized: bool
