from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Literal

import structlog
from botbuilder.core import BotFrameworkAdapter, TurnContext
from botbuilder.schema import (
    Activity,
    Attachment,
    ChannelAccount,
    ConversationAccount,
    ConversationReference,
)

from sre_agent.domain.entities.incident import Incident
from sre_agent.domain.ports.notification import (
    ApprovalCardPayload,
    ApprovalNotificationPort,
    StatusNotificationPort,
)
from sre_agent.infrastructure.messaging.adaptive_cards import (
    build_approval_card,
    build_incident_update_card,
    build_resolution_card,
)


log = structlog.get_logger(__name__)


class ConversationReferenceStore:
    """Tracks the ConversationReference needed to proactively message a user/channel.

    In Teams, a reference is established the first time a user interacts with the bot.
    We index references by EVERY identifier we can extract from the incoming activity
    (AAD object ID, display name, email/UPN if Teams sent it) so the agent can look up
    by whatever string it has — usually the email/UPN from the on-call YAML.

    References are persisted to JSON on disk so they survive agent restarts. The path
    is `CONV_REF_STORE_PATH` env var (default: /app/data/conversation_refs.json).
    """

    def __init__(self, persist_path: str | None = None) -> None:
        self._by_user: dict[str, ConversationReference] = {}
        self._by_channel: dict[str, ConversationReference] = {}
        self._persist_path = persist_path or os.environ.get(
            "CONV_REF_STORE_PATH", "/app/data/conversation_refs.json"
        )
        self._load()

    def _load(self) -> None:
        try:
            p = Path(self._persist_path)
            if not p.exists():
                return
            with p.open() as f:
                data = json.load(f)
            for key, raw in (data.get("users") or {}).items():
                try:
                    self._by_user[key] = ConversationReference().deserialize(raw)
                except Exception:
                    log.exception("conv_refs: failed to load user", key=key)
            for key, raw in (data.get("channels") or {}).items():
                try:
                    self._by_channel[key] = ConversationReference().deserialize(raw)
                except Exception:
                    log.exception("conv_refs: failed to load channel", key=key)
            log.info(
                "conv_refs: loaded from disk",
                path=self._persist_path,
                users=len(self._by_user),
                channels=len(self._by_channel),
            )
        except Exception:
            log.exception("conv_refs: load failed", path=self._persist_path)

    def _persist(self) -> None:
        try:
            p = Path(self._persist_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "users": {k: v.serialize() for k, v in self._by_user.items()},
                "channels": {k: v.serialize() for k, v in self._by_channel.items()},
            }
            # Atomic write
            with tempfile.NamedTemporaryFile(
                "w", dir=str(p.parent), delete=False
            ) as f:
                json.dump(data, f)
                tmp = f.name
            os.replace(tmp, p)
        except Exception:
            log.exception("conv_refs: persist failed", path=self._persist_path)

    def save_from_activity(self, activity: Activity) -> None:
        ref = TurnContext.get_conversation_reference(activity)
        keys: set[str] = set()
        fp = activity.from_property
        if fp:
            if getattr(fp, "aad_object_id", None):
                keys.add(fp.aad_object_id)
            if getattr(fp, "name", None):
                keys.add(fp.name)
            if getattr(fp, "id", None):
                keys.add(fp.id)
            # Teams sticks the user's email/UPN in additional_properties
            extra = getattr(fp, "additional_properties", None) or {}
            for k in ("email", "upn", "userPrincipalName", "aadObjectId"):
                v = extra.get(k) if isinstance(extra, dict) else None
                if v:
                    keys.add(str(v))
            # When the activity has channelData with tenant + user info (Teams)
            ch_data = activity.channel_data or {}
            if isinstance(ch_data, dict):
                from_data = ch_data.get("from") or {}
                for k in ("aadObjectId", "userPrincipalName", "email"):
                    v = from_data.get(k)
                    if v:
                        keys.add(str(v))
        for raw in keys:
            if not raw:
                continue
            self._by_user[raw] = ref
            self._by_user[raw.lower()] = ref
        if activity.conversation:
            self._by_channel[activity.conversation.id] = ref
        self._persist()

    def get_for_user(self, user: str) -> ConversationReference | None:
        return self._by_user.get(user) or self._by_user.get(user.lower())

    def get_for_channel(self, channel_id: str) -> ConversationReference | None:
        return self._by_channel.get(channel_id)

    def any_user_ref(self) -> ConversationReference | None:
        """Return any registered user — for demo fallback when the addressed user
        hasn't DM'd the bot yet. Returns None if no user has ever DM'd."""
        return next(iter(self._by_user.values()), None)

    def all_users(self) -> list[str]:
        return sorted(self._by_user.keys())


class TeamsApprovalNotificationAdapter(ApprovalNotificationPort):
    def __init__(
        self,
        *,
        adapter: BotFrameworkAdapter,
        bot_app_id: str,
        references: ConversationReferenceStore,
    ) -> None:
        self._adapter = adapter
        self._bot_app_id = bot_app_id
        self._refs = references

    async def request_approval(
        self,
        *,
        to_user: str,
        payload: ApprovalCardPayload,
    ) -> str:
        card = build_approval_card(
            approval=payload.approval,
            incident=payload.incident,
            rationale=payload.rationale,
            metrics_summary=payload.metrics_summary,
        )
        return await self._send_card(to_user=to_user, card=card)

    async def update_approval_message(
        self,
        *,
        to_user: str,
        thread_id: str,
        final_status: Literal["approved", "rejected", "timed_out", "escalated"],
        decided_by: str | None = None,
    ) -> None:
        text = f"Approval {final_status}"
        if decided_by:
            text = f"{text} by {decided_by}"
        await self._send_text(to_user=to_user, text=text)

    async def _send_card(self, *, to_user: str, card: dict[str, object]) -> str:
        ref = self._refs.get_for_user(to_user)
        if ref is None:
            # Demo fallback: if the targeted user hasn't DM'd the bot yet, send the
            # card to any user that has — so the demo never silently swallows it.
            ref = self._refs.any_user_ref()
            if ref is None:
                log.warning(
                    "no conversation reference at all (no user has DM'd the bot yet)",
                    target=to_user,
                )
                return ""
            log.warning(
                "addressed user has not DM'd the bot — falling back to first registered user",
                target=to_user,
                fallback_to=getattr(ref.user, "id", "unknown"),
                known_users=self._refs.all_users(),
            )

        activity = Activity(
            type="message",
            attachments=[
                Attachment(
                    content_type="application/vnd.microsoft.card.adaptive", content=card
                )
            ],
        )
        sent_id: list[str] = []

        async def _send(turn: TurnContext) -> None:
            response = await turn.send_activity(activity)
            if response and response.id:
                sent_id.append(response.id)

        await self._adapter.continue_conversation(ref, _send, self._bot_app_id)
        return sent_id[0] if sent_id else ""

    async def _send_text(self, *, to_user: str, text: str) -> None:
        ref = self._refs.get_for_user(to_user) or self._refs.any_user_ref()
        if ref is None:
            log.warning("_send_text: no conversation reference available", target=to_user)
            return
        activity = Activity(type="message", text=text)

        async def _send(turn: TurnContext) -> None:
            await turn.send_activity(activity)

        await self._adapter.continue_conversation(ref, _send, self._bot_app_id)


class TeamsStatusNotificationAdapter(StatusNotificationPort):
    def __init__(
        self,
        *,
        adapter: BotFrameworkAdapter,
        bot_app_id: str,
        references: ConversationReferenceStore,
        default_channel_id: str | None = None,
    ) -> None:
        self._adapter = adapter
        self._bot_app_id = bot_app_id
        self._refs = references
        self._default_channel = default_channel_id

    async def post_incident_update(
        self,
        *,
        incident: Incident,
        summary: str,
        channel_id: str | None = None,
    ) -> None:
        card = build_incident_update_card(incident=incident, summary=summary)
        channel = channel_id or self._default_channel
        if channel is not None:
            await self._post_card(channel_id=channel, card=card)
            return
        # No channel configured — DM the first registered user so status updates
        # (ticket created, SLA warning, etc.) land somewhere visible instead of
        # being silently dropped.
        ref = self._refs.any_user_ref()
        if ref is None:
            log.warning("status update dropped: no channel + no registered user")
            return
        await self._send_card_via_ref(ref, card)

    async def post_resolution(self, *, incident: Incident, summary: str) -> None:
        card = build_resolution_card(incident=incident, summary=summary)
        if self._default_channel is not None:
            await self._post_card(channel_id=self._default_channel, card=card)
            return
        ref = self._refs.any_user_ref()
        if ref is None:
            return
        await self._send_card_via_ref(ref, card)

    async def _send_card_via_ref(self, ref: ConversationReference, card: dict[str, object]) -> None:
        activity = Activity(
            type="message",
            attachments=[
                Attachment(
                    content_type="application/vnd.microsoft.card.adaptive", content=card
                )
            ],
        )

        async def _send(turn: TurnContext) -> None:
            await turn.send_activity(activity)

        await self._adapter.continue_conversation(ref, _send, self._bot_app_id)

    async def _post_card(self, *, channel_id: str, card: dict[str, object]) -> None:
        ref = self._refs.get_for_channel(channel_id)
        if ref is None:
            # Construct a minimal reference if we know the channel
            ref = ConversationReference(
                channel_id="msteams",
                bot=ChannelAccount(id=self._bot_app_id),
                conversation=ConversationAccount(id=channel_id),
            )
        activity = Activity(
            type="message",
            attachments=[
                Attachment(
                    content_type="application/vnd.microsoft.card.adaptive", content=card
                )
            ],
        )

        async def _send(turn: TurnContext) -> None:
            await turn.send_activity(activity)

        await self._adapter.continue_conversation(ref, _send, self._bot_app_id)
