from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from sre_agent.domain.entities.incident import Incident
from sre_agent.domain.value_objects import ServiceName
from sre_agent.infrastructure.persistence.models import Base
from sre_agent.infrastructure.persistence.postgres.uow import (
    SqlAlchemyUnitOfWork,
    make_session_factory,
)


pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def session_factory() -> object:
    dsn = os.environ.get(
        "POSTGRES_DSN", "postgresql+asyncpg://sre:sre@localhost:5432/sre_agent_test"
    )
    engine = create_async_engine(dsn)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = make_session_factory(dsn)
    yield factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_incident_roundtrip(session_factory: object) -> None:
    incident = Incident.detect(
        service=ServiceName("payments-api"),
        initial_signal="503 spike",
        signal_sources=("prometheus",),
    )
    incident.drain_events()

    uow = SqlAlchemyUnitOfWork(session_factory)  # type: ignore[arg-type]
    async with uow as u:
        await u.incidents.add(incident)
        await u.commit()

    uow2 = SqlAlchemyUnitOfWork(session_factory)  # type: ignore[arg-type]
    async with uow2 as u:
        loaded = await u.incidents.get(incident.id)

    assert loaded is not None
    assert loaded.service == ServiceName("payments-api")
    assert loaded.initial_signal == "503 spike"
