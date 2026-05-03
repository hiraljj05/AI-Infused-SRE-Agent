from __future__ import annotations

import base64
from typing import Any

import httpx
import structlog

from sre_agent.domain.ports.ticketing import CreatedTicket, TicketDraft, TicketingPort

log = structlog.get_logger(__name__)


_PRIORITY_MAP = {
    "P0": "Highest",
    "P1": "High",
    "P2": "Medium",
    "P3": "Low",
    "P4": "Lowest",
}


class JiraCloudAdapter(TicketingPort):
    """Atlassian Cloud REST API v3 adapter.

    Auth uses email + API token. Get a token at https://id.atlassian.com/manage-profile/security/api-tokens.
    """

    def __init__(
        self,
        *,
        base_url: str,  # e.g. https://your-org.atlassian.net
        email: str,
        api_token: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=timeout_seconds,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def create_ticket(self, draft: TicketDraft) -> CreatedTicket:
        priority = _PRIORITY_MAP.get(draft.priority, "Medium")
        body: dict[str, Any] = {
            "fields": {
                "project": {"key": draft.project_key},
                "summary": draft.summary,
                "description": _to_adf(draft.description),
                "issuetype": {"name": "Incident"},
                "priority": {"name": priority},
                "labels": list(draft.labels),
            }
        }
        # If your Jira doesn't have "Incident" issuetype, fall back to "Task".
        r = await self._client.post(f"{self._base_url}/rest/api/3/issue", json=body)
        if r.status_code == 400 and "issuetype" in r.text.lower():
            body["fields"]["issuetype"] = {"name": "Task"}
            r = await self._client.post(f"{self._base_url}/rest/api/3/issue", json=body)
        r.raise_for_status()
        data = r.json()
        key = data["key"]
        url = f"{self._base_url}/browse/{key}"
        log.info("jira ticket created", key=key, url=url)
        return CreatedTicket(key=key, url=url)

    async def add_comment(self, ticket_key: str, comment: str) -> None:
        body = {"body": _to_adf(comment)}
        r = await self._client.post(
            f"{self._base_url}/rest/api/3/issue/{ticket_key}/comment", json=body
        )
        r.raise_for_status()

    async def get_ticket_status(self, ticket_key: str) -> str | None:
        try:
            r = await self._client.get(
                f"{self._base_url}/rest/api/3/issue/{ticket_key}",
                params={"fields": "status"},
            )
            if r.status_code == 404:
                # Stale key (e.g. ticket deleted, or imported from another env). Skip
                # quietly — the poller will keep trying but we don't need a stack trace.
                log.warning("jira ticket not found", key=ticket_key)
                return None
            r.raise_for_status()
            data = r.json()
            status = data.get("fields", {}).get("status", {})
            name = status.get("name")
            if isinstance(name, str) and name:
                return name
            return None
        except Exception:
            log.exception("jira get_ticket_status failed", key=ticket_key)
            return None

    async def transition_to_resolved(self, ticket_key: str, resolution: str) -> None:
        # Discover transition id for "Done"/"Resolved"
        r = await self._client.get(
            f"{self._base_url}/rest/api/3/issue/{ticket_key}/transitions"
        )
        r.raise_for_status()
        transitions = r.json().get("transitions", [])
        target = next(
            (t for t in transitions if t["name"].lower() in ("done", "resolved", "close")),
            None,
        )
        if target is None:
            log.warning("no resolved transition found", key=ticket_key)
            return
        await self._client.post(
            f"{self._base_url}/rest/api/3/issue/{ticket_key}/transitions",
            json={"transition": {"id": target["id"]}},
        )
        await self.add_comment(ticket_key, f"Resolved: {resolution}")


def _to_adf(text: str) -> dict[str, Any]:
    """Wrap plain text into Atlassian Document Format (ADF) — Jira Cloud's required format."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": line}],
            }
            for line in (text.split("\n") if text else [""])
        ],
    }
