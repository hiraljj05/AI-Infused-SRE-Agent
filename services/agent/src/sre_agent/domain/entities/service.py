from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sre_agent.domain.value_objects import ServiceName


class ServiceTier(str, Enum):
    TIER_0 = "tier-0"
    TIER_1 = "tier-1"
    TIER_2 = "tier-2"
    TIER_3 = "tier-3"

    @property
    def criticality_weight(self) -> float:
        return {
            ServiceTier.TIER_0: 1.0,
            ServiceTier.TIER_1: 0.75,
            ServiceTier.TIER_2: 0.5,
            ServiceTier.TIER_3: 0.25,
        }[self]


@dataclass(frozen=True, slots=True, kw_only=True)
class SLOTarget:
    metric: str
    target_percent: float
    window_days: int = 30


@dataclass(slots=True, kw_only=True)
class Service:
    name: ServiceName
    tier: ServiceTier
    namespace: str
    owner_primary: str
    owner_secondary: str | None = None
    incident_commander_group: str = "incident-commanders"
    dependencies: tuple[ServiceName, ...] = field(default_factory=tuple)
    slos: tuple[SLOTarget, ...] = field(default_factory=tuple)
    runbook_ids: tuple[str, ...] = field(default_factory=tuple)

    def user_impact_weight(self) -> float:
        return self.tier.criticality_weight
