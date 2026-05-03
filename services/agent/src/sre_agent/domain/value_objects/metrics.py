from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MetricSample:
    timestamp: datetime
    value: float
    labels: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def labels_dict(self) -> dict[str, str]:
        return dict(self.labels)


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    name: str
    samples: tuple[MetricSample, ...]

    @property
    def latest(self) -> MetricSample | None:
        return self.samples[-1] if self.samples else None

    @property
    def values(self) -> list[float]:
        return [s.value for s in self.samples]

    def mean(self) -> float:
        values = self.values
        return sum(values) / len(values) if values else 0.0

    def stdev(self) -> float:
        values = self.values
        return statistics.stdev(values) if len(values) >= 2 else 0.0

    def zscore(self, value: float) -> float:
        stdev = self.stdev()
        return (value - self.mean()) / stdev if stdev > 0 else 0.0

    def is_anomalous(self, threshold_zscore: float = 3.0) -> bool:
        latest = self.latest
        if latest is None or len(self.samples) < 10:
            return False
        return abs(self.zscore(latest.value)) >= threshold_zscore
