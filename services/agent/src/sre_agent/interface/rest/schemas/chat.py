from __future__ import annotations

from pydantic import BaseModel, Field


class ChatQueryIn(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    service: str | None = None


class ChatQueryOut(BaseModel):
    answer: str
    cited_docs: list[str]
    model: str
