from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BlastRadiusLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class BlastRadius:
    level: BlastRadiusLevel
    affected_services: tuple[str, ...] = field(default_factory=tuple)
    estimated_users_affected: int = 0
    estimated_downtime_seconds: int = 0
    reversible: bool = True

    @classmethod
    def low(cls, service: str) -> BlastRadius:
        return cls(
            level=BlastRadiusLevel.LOW,
            affected_services=(service,),
            estimated_users_affected=0,
            estimated_downtime_seconds=10,
            reversible=True,
        )

    @classmethod
    def critical(cls, services: tuple[str, ...], users: int, downtime: int) -> BlastRadius:
        return cls(
            level=BlastRadiusLevel.CRITICAL,
            affected_services=services,
            estimated_users_affected=users,
            estimated_downtime_seconds=downtime,
            reversible=False,
        )

    @property
    def requires_hil(self) -> bool:
        return self.level in (BlastRadiusLevel.HIGH, BlastRadiusLevel.CRITICAL) or not self.reversible

    @property
    def human_readable(self) -> str:
        svc = ", ".join(self.affected_services) or "unknown"
        reversibility = "reversible" if self.reversible else "IRREVERSIBLE"
        return (
            f"{self.level.value.upper()} - services=[{svc}] "
            f"users~{self.estimated_users_affected} downtime~{self.estimated_downtime_seconds}s "
            f"({reversibility})"
        )
