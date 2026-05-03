from __future__ import annotations

import structlog

from sre_agent.domain.ports.ticketing import EmailMessage, EmailPort

log = structlog.get_logger(__name__)


class LogOnlyEmailAdapter(EmailPort):
    """Dev / fallback adapter that logs emails instead of sending."""

    async def send(self, message: EmailMessage) -> None:
        log.info(
            "email (log-only)",
            to=message.to,
            cc=message.cc or [],
            subject=message.subject,
            body_preview=message.body_text[:200],
        )
