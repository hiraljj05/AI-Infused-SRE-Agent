from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("TimeWindow requires timezone-aware datetimes")
        if self.end < self.start:
            raise ValueError("TimeWindow end must be >= start")

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    @classmethod
    def last(cls, seconds: int, *, now: datetime | None = None) -> TimeWindow:
        end = now or datetime.now(UTC)
        return cls(start=end - timedelta(seconds=seconds), end=end)

    @classmethod
    def last_minutes(cls, minutes: int, *, now: datetime | None = None) -> TimeWindow:
        return cls.last(seconds=minutes * 60, now=now)

    def contains(self, ts: datetime) -> bool:
        return self.start <= ts <= self.end
