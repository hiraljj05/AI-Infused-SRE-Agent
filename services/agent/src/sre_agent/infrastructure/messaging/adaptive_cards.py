from __future__ import annotations

from typing import Any

from sre_agent.domain.entities.approval import Approval
from sre_agent.domain.entities.incident import Incident


def build_approval_card(*, approval: Approval, incident: Incident, rationale: str, metrics_summary: str) -> dict[str, Any]:
    action = incident.proposed_action
    top = incident.top_hypothesis
    blast = action.blast_radius if action else None

    facts = [
        {"title": "Incident", "value": str(incident.id)},
        {"title": "Service", "value": str(incident.service)},
        {"title": "Severity", "value": (incident.severity.value if incident.severity else "n/a")},
    ]
    if incident.jira_ticket_key:
        if incident.jira_ticket_url:
            facts.append(
                {
                    "title": "Jira",
                    "value": f"[{incident.jira_ticket_key}]({incident.jira_ticket_url})",
                }
            )
        else:
            facts.append({"title": "Jira", "value": incident.jira_ticket_key})
    facts += [
        {"title": "Proposed action", "value": action.name if action else "n/a"},
        {"title": "Action confidence", "value": f"{action.confidence}" if action else "n/a"},
        {"title": "RCA confidence", "value": f"{top.confidence}" if top else "n/a"},
        {
            "title": "Blast radius",
            "value": blast.human_readable if blast else "n/a",
        },
    ]
    body = [
        {
            "type": "TextBlock",
            "text": "SRE Agent - Remediation Approval",
            "weight": "Bolder",
            "size": "Large",
        },
        {"type": "FactSet", "facts": facts},
        {
            "type": "TextBlock",
            "text": f"**RCA top hypothesis**: {top.description if top else '(none)'}",
            "wrap": True,
        },
        {
            "type": "TextBlock",
            "text": f"**Action rationale**: {rationale}",
            "wrap": True,
            "spacing": "Small",
        },
    ]
    if metrics_summary:
        body.append(
            {
                "type": "TextBlock",
                "text": f"**Metrics**: {metrics_summary}",
                "wrap": True,
                "spacing": "Small",
            }
        )

    body.append(
        {
            "type": "Input.Text",
            "id": "reason",
            "label": "Rejection reason (optional)",
            "isMultiline": True,
            "placeholder": "Why rejecting? (only used if you click Reject)",
            "isRequired": False,
        }
    )

    actions: list[dict[str, Any]] = [
        {
            "type": "Action.Submit",
            "title": "Approve",
            "style": "positive",
            "data": {"approval_id": str(approval.id), "decision": "approve"},
        },
        {
            "type": "Action.Submit",
            "title": "Reject",
            "style": "destructive",
            "data": {"approval_id": str(approval.id), "decision": "reject"},
        },
    ]
    if incident.jira_ticket_url:
        actions.append(
            {
                "type": "Action.OpenUrl",
                "title": f"Open {incident.jira_ticket_key or 'Jira ticket'}",
                "url": incident.jira_ticket_url,
            }
        )
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "msteams": {"width": "Full"},
        "body": body,
        "actions": actions,
    }


def build_incident_update_card(*, incident: Incident, summary: str) -> dict[str, Any]:
    facts = [
        {"title": "Service", "value": str(incident.service)},
        {"title": "Severity", "value": (incident.severity.value if incident.severity else "n/a")},
        {"title": "Status", "value": incident.status.value},
    ]
    if incident.jira_ticket_key:
        facts.append(
            {
                "title": "Jira",
                "value": (
                    f"[{incident.jira_ticket_key}]({incident.jira_ticket_url})"
                    if incident.jira_ticket_url
                    else incident.jira_ticket_key
                ),
            }
        )
    card: dict[str, Any] = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"Incident update - {incident.id}",
                "weight": "Bolder",
                "size": "Medium",
            },
            {"type": "FactSet", "facts": facts},
            {"type": "TextBlock", "text": summary, "wrap": True},
        ],
    }
    if incident.jira_ticket_url:
        card["actions"] = [
            {
                "type": "Action.OpenUrl",
                "title": f"Open {incident.jira_ticket_key or 'Jira ticket'}",
                "url": incident.jira_ticket_url,
            }
        ]
    return card


def build_resolution_card(*, incident: Incident, summary: str) -> dict[str, Any]:
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"Incident resolved - {incident.id}",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Good",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Service", "value": str(incident.service)},
                    {"title": "Severity", "value": (incident.severity.value if incident.severity else "n/a")},
                    {"title": "Resolution", "value": summary[:140]},
                ],
            },
        ],
    }
