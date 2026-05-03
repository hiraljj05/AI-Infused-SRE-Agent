from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sre_agent.domain.ports.registry import AppRepository, ProjectRepository
from sre_agent.domain.ports.repositories import (
    ApprovalRepository,
    EventStore,
    IncidentRepository,
    PostmortemRepository,
    UnitOfWork,
)
from sre_agent.infrastructure.persistence.postgres.registry_repos import (
    SqlAlchemyAppRepository,
    SqlAlchemyProjectRepository,
)
from sre_agent.infrastructure.persistence.postgres.repositories import (
    SqlAlchemyApprovalRepository,
    SqlAlchemyEventStore,
    SqlAlchemyIncidentRepository,
    SqlAlchemyPostmortemRepository,
)
from sre_agent.infrastructure.persistence.postgres.sla_repo import (
    SqlAlchemySLATrackerRepository,
)
from sre_agent.infrastructure.persistence.postgres.lessons_repo import (
    SqlAlchemyLessonsRepository,
)
from sre_agent.domain.ports.lessons import LessonsRepository
from sre_agent.domain.ports.sla import SLATrackerRepository


class SqlAlchemyUnitOfWork(UnitOfWork):
    incidents: IncidentRepository
    approvals: ApprovalRepository
    postmortems: PostmortemRepository
    events: EventStore
    projects: ProjectRepository
    apps: AppRepository
    slas: SLATrackerRepository
    lessons: LessonsRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.incidents = SqlAlchemyIncidentRepository(self._session)
        self.approvals = SqlAlchemyApprovalRepository(self._session)
        self.postmortems = SqlAlchemyPostmortemRepository(self._session)
        self.events = SqlAlchemyEventStore(self._session)
        self.projects = SqlAlchemyProjectRepository(self._session)
        self.apps = SqlAlchemyAppRepository(self._session)
        self.slas = SqlAlchemySLATrackerRepository(self._session)
        self.lessons = SqlAlchemyLessonsRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._session is None:
            return
        try:
            if exc is not None:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("UnitOfWork not entered")
        await self._session.commit()

    async def rollback(self) -> None:
        if self._session is None:
            return
        await self._session.rollback()


def make_engine(dsn: str, *, echo: bool = False) -> AsyncEngine:
    """Build the single shared async engine for the agent process.

    Both the UnitOfWork session factory and the pgvector adapters bind to this
    engine so they share one connection pool (default size 10 + 10 overflow).

    SSL handling: asyncpg's URL parser doesn't accept ?ssl=... query params, so
    if the DSN includes one, we strip it and translate to connect_args. This
    lets .env stay declarative ("?ssl=require" for Azure / RDS) while still
    talking to plain-text local Postgres when no ssl param is set.
    """
    from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

    parts = urlsplit(dsn)
    query = parse_qs(parts.query, keep_blank_values=True)
    ssl_value = (query.pop("ssl", []) + query.pop("sslmode", []))
    connect_args: dict[str, object] = {}
    if ssl_value:
        # asyncpg accepts "require" / "prefer" / "disable" / etc. as a string,
        # or a bool, or an SSLContext. We normalize to strings; "true"/"1" mean
        # "require" for backwards-compat with common conventions.
        v = ssl_value[0].lower()
        if v in ("true", "1"):
            v = "require"
        connect_args["ssl"] = v
    cleaned_dsn = urlunsplit(parts._replace(query=urlencode(query, doseq=True)))
    return create_async_engine(
        cleaned_dsn,
        echo=echo,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
        connect_args=connect_args,
    )


def make_session_factory(
    dsn_or_engine: str | AsyncEngine, *, echo: bool = False
) -> async_sessionmaker[AsyncSession]:
    engine = (
        dsn_or_engine
        if isinstance(dsn_or_engine, AsyncEngine)
        else make_engine(dsn_or_engine, echo=echo)
    )
    return async_sessionmaker(bind=engine, expire_on_commit=False)
