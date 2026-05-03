from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from sre_agent.domain.ports.llm import LLMMessage, LLMPort


Intent = Literal[
    "query",  # general Q&A about runbooks/services/incidents
    "investigate_app",  # "what's wrong with X" -> run gather+diagnose for that service
    "propose_action",  # "suggest a fix for X" -> investigate+propose, don't execute
    "execute_action",  # "restart pod X", "scale Y to 5" -> propose+request HIL
    "show_history",  # "show last incidents on X"
]


INTENT_SYSTEM_PROMPT = """You are an intent classifier for an SRE operator chatbot. Classify the user's
message into one of these intents and extract structured fields.

Intents:
  - query             : general question about services / runbooks / on-call (no action)
  - investigate_app   : user wants to know what's currently wrong with an app
  - propose_action    : user wants a fix recommendation (no execution)
  - execute_action    : user wants the agent to perform a specific action now
  - show_history      : user wants past incidents / postmortems

Fields to extract when present:
  - app: the service name (e.g., "payments-api")
  - action: one of restart_pod, rollout_restart, scale_deployment, patch_memory_limit,
            patch_cpu_limit, cordon_node, rollback_deployment, exec_into_pod, kubectl_exec,
            no_op_escalate (only for execute_action / propose_action)
  - parameters: object with action-specific keys (namespace, pod_name, replicas, ...)
  - time_range: ISO duration like "P7D" if user implies a window

Return JSON; absent fields = null/empty.
"""


INTENT_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["intent"],
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "query",
                "investigate_app",
                "propose_action",
                "execute_action",
                "show_history",
            ],
        },
        "app": {"type": ["string", "null"]},
        "action": {"type": ["string", "null"]},
        "parameters": {"type": ["object", "null"]},
        "time_range": {"type": ["string", "null"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
}


@dataclass(frozen=True, slots=True, kw_only=True)
class ParseIntentInput:
    text: str


@dataclass(slots=True, kw_only=True)
class ParsedIntent:
    intent: Intent
    app: str | None = None
    action: str | None = None
    parameters: dict[str, Any] | None = None
    time_range: str | None = None
    confidence: float = 0.0


class ParseChatIntentUseCase:
    def __init__(self, *, llm: LLMPort) -> None:
        self._llm = llm

    async def execute(self, input_: ParseIntentInput) -> ParsedIntent:
        response = await self._llm.complete_structured(
            messages=[
                LLMMessage(role="system", content=INTENT_SYSTEM_PROMPT),
                LLMMessage(role="user", content=input_.text),
            ],
            json_schema=INTENT_JSON_SCHEMA,
            temperature=0.0,
            max_tokens=300,
        )
        data = response.structured or json.loads(response.content)
        return ParsedIntent(
            intent=data["intent"],
            app=data.get("app"),
            action=data.get("action"),
            parameters=data.get("parameters"),
            time_range=data.get("time_range"),
            confidence=float(data.get("confidence", 0.5)),
        )
