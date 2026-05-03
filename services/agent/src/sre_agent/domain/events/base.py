from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: uuid.UUID | None = None
    causation_id: uuid.UUID | None = None
    caused_by: str = "agent"

    @property
    def event_type(self) -> str:
        return type(self).__name__

    @property
    def version(self) -> int:
        return 1
