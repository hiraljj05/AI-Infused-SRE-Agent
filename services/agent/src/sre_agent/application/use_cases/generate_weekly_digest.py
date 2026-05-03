from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sre_agent.domain.entities.incident import IncidentStatus
from sre_agent.domain.ports.repositories import UnitOfWork


@dataclass(frozen=True, slots=True, kw_only=True)
class WeeklyDigest:
    period_start: datetime
    period_end: datetime
    total_incidents: int
    new_incidents: int
    resolved_incidents: int
    by_severity: dict[str, int]
    by_service: list[tuple[str, int]]
    avg_mttr_minutes: float
    agent_resolutions: int
    human_resolutions: int
    agent_share_pct: int
    top_categories: list[tuple[str, int]]
    open_breached_slas: int
    summary_markdown: str


class GenerateWeeklyDigestUseCase:
    """Aggregates the last 7 days of incidents + lessons into a digest object."""

    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, days: int = 7) -> WeeklyDigest:
        end = datetime.now(UTC)
        start = end - timedelta(days=days)

        async with self._uow as u:
            all_incidents: list = []
            for status in IncidentStatus:
                items = await u.incidents.list_by_status(status)
                all_incidents.extend(items)
            lessons = await u.lessons.list_recent(limit=500)
            try:
                open_slas = await u.slas.list_open()
            except Exception:
                open_slas = []

        in_window = [i for i in all_incidents if i.detected_at >= start]
        resolved_in_window = [i for i in in_window if i.status == IncidentStatus.RESOLVED]

        sev_counts: dict[str, int] = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
        for i in in_window:
            if i.severity is not None:
                sev_counts[i.severity.value] = sev_counts.get(i.severity.value, 0) + 1

        svc_counter: Counter = Counter(str(i.service) for i in in_window)
        top_services = svc_counter.most_common(5)

        lessons_window = [l for l in lessons if l.created_at >= start]
        agent = sum(1 for l in lessons_window if l.resolver == "agent")
        human = len(lessons_window) - agent
        avg_mttr = (
            sum(l.resolution_minutes for l in lessons_window) / len(lessons_window)
            if lessons_window
            else 0.0
        )
        cats = Counter(l.issue_category.value for l in lessons_window)
        top_cats = cats.most_common(5)
        agent_share = round((agent / len(lessons_window)) * 100) if lessons_window else 0

        breached = sum(1 for t in open_slas if t.status.value == "breached")

        svc_lines = (
            [f"- `{svc}` — {cnt} incidents" for svc, cnt in top_services]
            if top_services
            else ["- _(none)_"]
        )
        cat_lines = (
            [f"- {c} ({n})" for c, n in top_cats] if top_cats else ["- _(none)_"]
        )
        md_lines = [
            f"# SRE Weekly Digest — {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}",
            "",
            f"**{len(in_window)} incidents** detected in the last {days} days "
            f"(resolved: {len(resolved_in_window)}).",
            "",
            "## Severity",
            *[f"- **{sev}**: {cnt}" for sev, cnt in sev_counts.items()],
            "",
            "## Top services",
            *svc_lines,
            "",
            "## Resolution breakdown",
            f"- 🤖 **Agent**: {agent} ({agent_share}%)",
            f"- 👤 **Human**: {human}",
            f"- ⏱ **Avg MTTR**: {round(avg_mttr, 1)} min",
            "",
            "## Top issue categories",
            *cat_lines,
            "",
            f"## Open SLA breaches: **{breached}**",
        ]
        summary = "\n".join(md_lines)

        return WeeklyDigest(
            period_start=start,
            period_end=end,
            total_incidents=len(all_incidents),
            new_incidents=len(in_window),
            resolved_incidents=len(resolved_in_window),
            by_severity=sev_counts,
            by_service=top_services,
            avg_mttr_minutes=round(avg_mttr, 1),
            agent_resolutions=agent,
            human_resolutions=human,
            agent_share_pct=agent_share,
            top_categories=top_cats,
            open_breached_slas=breached,
            summary_markdown=summary,
        )
