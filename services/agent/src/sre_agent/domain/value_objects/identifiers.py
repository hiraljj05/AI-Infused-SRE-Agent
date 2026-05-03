from __future__ import annotations

import re
import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IncidentId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.startswith("INC-"):
            raise ValueError(f"IncidentId must start with 'INC-', got {self.value!r}")

    @classmethod
    def new(cls) -> IncidentId:
        return cls(value=f"INC-{uuid.uuid4().hex[:12].upper()}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ApprovalId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.startswith("appr_"):
            raise ValueError(f"ApprovalId must start with 'appr_', got {self.value!r}")

    @classmethod
    def new(cls) -> ApprovalId:
        return cls(value=f"appr_{uuid.uuid4().hex}")

    def __str__(self) -> str:
        return self.value


_SERVICE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")


@dataclass(frozen=True, slots=True)
class ServiceName:
    value: str

    def __post_init__(self) -> None:
        if not _SERVICE_NAME_PATTERN.match(self.value):
            raise ValueError(
                f"ServiceName must be DNS-label-like (lowercase, digits, hyphens), got {self.value!r}"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PodIdentifier:
    namespace: str
    name: str

    def __post_init__(self) -> None:
        if not self.namespace or not self.name:
            raise ValueError("PodIdentifier namespace and name are required")

    @property
    def qualified(self) -> str:
        return f"{self.namespace}/{self.name}"

    def __str__(self) -> str:
        return self.qualified
