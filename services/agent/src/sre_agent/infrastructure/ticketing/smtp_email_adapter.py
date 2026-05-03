from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage as Email

import structlog

from sre_agent.domain.ports.ticketing import EmailMessage, EmailPort

log = structlog.get_logger(__name__)


class SmtpEmailAdapter(EmailPort):
    """Plain SMTP adapter (TLS optional). Works with Gmail, SES, Outlook, etc."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        use_tls: bool = True,
        timeout_seconds: int = 15,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from = from_address
        self._use_tls = use_tls
        self._timeout = timeout_seconds

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        msg = Email()
        msg["From"] = self._from
        msg["To"] = ", ".join(message.to)
        if message.cc:
            msg["Cc"] = ", ".join(message.cc)
        msg["Subject"] = message.subject
        msg.set_content(message.body_text)
        if message.body_html:
            msg.add_alternative(message.body_html, subtype="html")

        recipients = list(message.to) + (message.cc or [])
        if self._use_tls:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as s:
                s.starttls(context=ssl.create_default_context())
                if self._username:
                    s.login(self._username, self._password)
                s.send_message(msg, from_addr=self._from, to_addrs=recipients)
        else:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as s:
                if self._username:
                    s.login(self._username, self._password)
                s.send_message(msg, from_addr=self._from, to_addrs=recipients)
        log.info("email sent", to=message.to, subject=message.subject)
