from __future__ import annotations

from pathlib import Path

import yaml

from sre_agent.domain.entities.service import Service, ServiceTier, SLOTarget
from sre_agent.domain.ports.knowledge import EscalationLookupPort, ServiceCatalogPort
from sre_agent.domain.value_objects import ServiceName


class YamlServiceCatalogAdapter(ServiceCatalogPort):
    """Loads service definitions from a YAML directory (one file per service)."""

    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)
        self._cache: dict[str, Service] | None = None

    async def get(self, name: ServiceName) -> Service | None:
        return self._load().get(str(name))

    async def list_all(self) -> list[Service]:
        return list(self._load().values())

    def _load(self) -> dict[str, Service]:
        if self._cache is not None:
            return self._cache
        services: dict[str, Service] = {}
        for path in sorted(self._directory.glob("*.yaml")):
            data = yaml.safe_load(path.read_text())
            if not data:
                continue
            slos = tuple(
                SLOTarget(
                    metric=s["metric"],
                    target_percent=float(s["target_percent"]),
                    window_days=int(s.get("window_days", 30)),
                )
                for s in data.get("slos", [])
            )
            svc = Service(
                name=ServiceName(data["name"]),
                tier=ServiceTier(data.get("tier", "tier-2")),
                namespace=data.get("namespace", "default"),
                owner_primary=data["owner_primary"],
                owner_secondary=data.get("owner_secondary"),
                incident_commander_group=data.get("incident_commander_group", "incident-commanders"),
                dependencies=tuple(ServiceName(d) for d in data.get("dependencies", [])),
                slos=slos,
                runbook_ids=tuple(data.get("runbook_ids", [])),
            )
            services[str(svc.name)] = svc
        self._cache = services
        return self._cache


class YamlEscalationLookupAdapter(EscalationLookupPort):
    def __init__(
        self,
        *,
        catalog: YamlServiceCatalogAdapter,
        default_commander_group: str = "incident-commanders",
        default_primary: str | None = None,
        default_secondary: str | None = None,
    ) -> None:
        self._catalog = catalog
        self._commander = default_commander_group
        self._default_primary = default_primary or default_commander_group
        self._default_secondary = default_secondary or default_commander_group

    async def _service_or_base(self, service: ServiceName):
        """Look up the service catalog. Falls back to the base name (strips a
        trailing -<digits> suffix) so synthetic chaos service names like
        `food-orders-711398` resolve to `food-orders`'s YAML."""
        svc = await self._catalog.get(service)
        if svc is not None:
            return svc
        import re
        base = re.sub(r"-\d{4,}$", "", str(service))
        if base != str(service):
            return await self._catalog.get(ServiceName(base))
        return None

    async def primary_for(self, service: ServiceName) -> str:
        svc = await self._service_or_base(service)
        return svc.owner_primary if svc else self._default_primary

    async def secondary_for(self, service: ServiceName) -> str | None:
        svc = await self._service_or_base(service)
        return svc.owner_secondary if svc else self._default_secondary

    async def commander_group(self) -> str:
        return self._commander
