from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfidenceScore:
    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Confidence must be in [0.0, 1.0], got {self.value}")

    @property
    def is_actionable(self) -> bool:
        return self.value >= 0.70

    @property
    def is_high(self) -> bool:
        return self.value >= 0.85

    @property
    def label(self) -> str:
        if self.value >= 0.85:
            return "high"
        if self.value >= 0.60:
            return "medium"
        if self.value >= 0.30:
            return "low"
        return "very-low"

    def __str__(self) -> str:
        return f"{self.value:.2f} ({self.label})"
