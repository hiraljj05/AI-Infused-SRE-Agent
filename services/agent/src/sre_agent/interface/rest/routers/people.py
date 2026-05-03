from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from sre_agent.interface.rest.dependencies import get_container

router = APIRouter(prefix="/api/people", tags=["people"])


class CategoryCount(BaseModel):
    category: str
    count: int


class PeopleAggregate(BaseModel):
    resolver: str
    total_resolutions: int
    agent_resolutions: int
    human_resolutions: int
    avg_resolution_minutes: float
    top_categories: list[CategoryCount]


@router.get("/aggregates", response_model=list[PeopleAggregate])
async def people_aggregates(container=Depends(get_container)) -> list[PeopleAggregate]:
    """Aggregates resolutions per resolver from the lessons-learnt corpus."""
    async with container.uow_factory() as uow:
        lessons = await uow.lessons.list_recent(limit=500)

    by_resolver: dict[str, list] = defaultdict(list)
    for l in lessons:
        by_resolver[l.resolver].append(l)

    out: list[PeopleAggregate] = []
    for resolver, items in by_resolver.items():
        agent_count = sum(1 for l in items if l.resolver == "agent")
        human_count = len(items) - agent_count
        avg_min = sum(l.resolution_minutes for l in items) / len(items) if items else 0.0
        cats = Counter(l.issue_category.value for l in items)
        top = [CategoryCount(category=c, count=n) for c, n in cats.most_common(3)]
        out.append(
            PeopleAggregate(
                resolver=resolver,
                total_resolutions=len(items),
                agent_resolutions=agent_count,
                human_resolutions=human_count,
                avg_resolution_minutes=round(avg_min, 1),
                top_categories=top,
            )
        )

    out.sort(key=lambda x: x.total_resolutions, reverse=True)
    return out
