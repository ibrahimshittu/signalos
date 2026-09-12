from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from signalos_backend.domain import utc_now
from signalos_backend.notifications.domain import (
    ExpoPushMessage,
    PushDevice,
    RegisterPushDevice,
)
from signalos_backend.notifications.gateway import ExpoPushError, ExpoPushGateway
from signalos_backend.notifications.store import NotificationStore
from signalos_backend.proposals.domain import TradeProposal
from signalos_backend.proposals.store import ProposalStore
from signalos_backend.security.credentials import CredentialCipher
from signalos_backend.users.domain import NotificationFrequency
from signalos_backend.users.store import UserStore


class NotificationService:
    def __init__(
        self,
        *,
        store: NotificationStore,
        cipher: CredentialCipher,
        gateway: ExpoPushGateway,
        users: UserStore | None = None,
        proposals: ProposalStore | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.store = store
        self.cipher = cipher
        self.gateway = gateway
        self.users = users
        self.proposals = proposals
        self.clock = clock

    async def register_device(
        self,
        *,
        user_id: str,
        installation_id: UUID,
        payload: RegisterPushDevice,
    ) -> PushDevice:
        token = payload.expo_push_token.get_secret_value()
        return await self.store.register_device(
            user_id=user_id,
            installation_id=installation_id,
            platform=payload.platform,
            expo_project_id=payload.expo_project_id,
            token_ciphertext=self.cipher.encrypt(token),
            token_fingerprint=hashlib.sha256(token.encode()).hexdigest(),
            now=self.clock().astimezone(UTC),
        )

    async def list_devices(self, *, user_id: str) -> tuple[PushDevice, ...]:
        return await self.store.list_devices(user_id=user_id)

    async def remove_device(self, *, user_id: str, installation_id: UUID) -> bool:
        return await self.store.remove_device(
            user_id=user_id,
            installation_id=installation_id,
        )

    async def notify_proposal(self, proposal: TradeProposal) -> None:
        if self.users is not None:
            profile = await self.users.get_profile(proposal.user_id)
            if (
                profile is None
                or profile.notification_frequency is not NotificationFrequency.OPPORTUNITIES_ONLY
            ):
                return
        now = self.clock().astimezone(UTC)
        deliveries = await self.store.prepare_deliveries(
            user_id=proposal.user_id,
            proposal_id=proposal.id,
            now=now,
        )
        if not deliveries:
            return
        messages = tuple(
            ExpoPushMessage(
                to=self.cipher.decrypt(delivery.token_ciphertext),
                title="New SignalOS proposal",
                body="A new proposal is ready for your private review.",
                data={"type": "proposal_available", "proposal_id": str(proposal.id)},
            )
            for delivery in deliveries
        )
        try:
            tickets = await self.gateway.send(messages)
        except ExpoPushError:
            for delivery in deliveries:
                await self.store.mark_ticket(
                    delivery_id=delivery.id,
                    ticket_id=None,
                    error_code="expo_request_failed",
                    now=self.clock().astimezone(UTC),
                )
            return
        for delivery, ticket in zip(deliveries, tickets, strict=True):
            await self.store.mark_ticket(
                delivery_id=delivery.id,
                ticket_id=ticket.id if ticket.status == "ok" else None,
                error_code=ticket.details.get("error") if ticket.status != "ok" else None,
                now=self.clock().astimezone(UTC),
            )

    async def reconcile_receipts(self) -> int:
        deliveries = await self.store.ticketed_deliveries()
        if not deliveries:
            return 0
        receipts = await self.gateway.receipts([delivery.expo_ticket_id for delivery in deliveries])
        updated = 0
        for delivery in deliveries:
            receipt = receipts.get(delivery.expo_ticket_id)
            if receipt is None:
                continue
            error_code = receipt.details.get("error")
            await self.store.mark_receipt(
                delivery_id=delivery.id,
                delivered=receipt.status == "ok",
                error_code=error_code,
                disable_device=error_code == "DeviceNotRegistered",
                now=self.clock().astimezone(UTC),
            )
            updated += 1
        return updated

    async def retry_failed(self) -> int:
        if self.proposals is None:
            return 0
        retried = 0
        for user_id, proposal_id in await self.store.failed_proposals():
            proposal = await self.proposals.get(user_id=user_id, proposal_id=proposal_id)
            if proposal is None:
                continue
            await self.notify_proposal(proposal)
            retried += 1
        return retried
