from __future__ import annotations

import pytest

from sre_agent.application.use_cases.detect_incident import (
    DetectIncidentCommand,
    DetectIncidentUseCase,
)
from sre_agent.domain.value_objects import ServiceName
from tests.fixtures.fake_uow import FakeUoW


@pytest.mark.asyncio
async def test_creates_new_incident_when_none_active() -> None:
    uow = FakeUoW()
    uc = DetectIncidentUseCase(uow)
    incident = await uc.execute(
        DetectIncidentCommand(
            service=ServiceName("payments-api"),
            initial_signal="error-rate spike",
            signal_sources=("prometheus",),
        )
    )
    assert incident.service == ServiceName("payments-api")
    assert uow.committed
    assert len(uow.events.events) >= 1


@pytest.mark.asyncio
async def test_deduplicates_existing_active_incident() -> None:
    uow = FakeUoW()
    uc = DetectIncidentUseCase(uow)
    first = await uc.execute(
        DetectIncidentCommand(
            service=ServiceName("payments-api"),
            initial_signal="spike",
            signal_sources=("prometheus",),
        )
    )
    uow.events.events.clear()
    second = await uc.execute(
        DetectIncidentCommand(
            service=ServiceName("payments-api"),
            initial_signal="another alert",
            signal_sources=("loki",),
        )
    )
    assert first.id == second.id
    assert not uow.events.events  # dedup -> no new events
