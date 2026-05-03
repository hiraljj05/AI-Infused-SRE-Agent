from __future__ import annotations

from enum import Enum
from typing import Self


class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

    @classmethod
    def from_score(cls, user_impact: float, blast_radius_weight: float, slo_burn: float) -> Self:
        score = user_impact * 0.5 + blast_radius_weight * 0.3 + slo_burn * 0.2
        if score >= 0.8:
            return cls(cls.P1)
        if score >= 0.5:
            return cls(cls.P2)
        if score >= 0.25:
            return cls(cls.P3)
        return cls(cls.P4)

    @property
    def mttd_target_seconds(self) -> int:
        return {Severity.P1: 180, Severity.P2: 600, Severity.P3: 1800, Severity.P4: 3600}[self]

    @property
    def mttr_target_seconds(self) -> int:
        return {
            Severity.P1: 3600,
            Severity.P2: 14400,
            Severity.P3: 86400,
            Severity.P4: 259200,
        }[self]

    @property
    def requires_incident_commander(self) -> bool:
        return self in (Severity.P1, Severity.P2)
