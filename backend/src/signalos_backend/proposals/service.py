from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from signalos_backend.brokers.domain import ConnectionStatus
from signalos_backend.brokers.store import BrokerStore
from signalos_backend.domain import utc_now
from signalos_backend.investment.personalization import FeedbackObservation, PreferenceLearner
from signalos_backend.proposals.domain import (
    CreateTradeProposal,
    ProposalFeedback,
    ProposalStatus,
    TradeProposal,
)
from signalos_backend.proposals.store import ProposalStore
from signalos_backend.users.memory import MemoryKind, MemorySource, UserMemoryStore
from signalos_backend.users.store import UserStore

logger = logging.getLogger(__name__)


class ProposalNotifier(Protocol):
    async def notify_proposal(self, proposal: TradeProposal) -> None: ...


class ProposalService:
    def __init__(
        self,
        *,
        users: UserStore,
        brokers: BrokerStore,
        proposals: ProposalStore,
        memories: UserMemoryStore | None = None,
        notifications: ProposalNotifier | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.users = users
        self.brokers = brokers
        self.proposals = proposals
        self.memories = memories
        self.notifications = notifications
        self.clock = clock

    async def create(self, *, user_id: str, payload: CreateTradeProposal) -> TradeProposal:
        if not payload.gate_report.passed:
            raise ValueError("mandatory gates did not pass")
        profile = await self.users.get_profile(user_id)
        if profile is None or not profile.disclosures_accepted:
            raise ValueError("investment profile and disclosures are required")
        connection = await self.brokers.get_connection(
            user_id=user_id, connection_id=payload.connection_id
        )
        if connection is None:
            raise ValueError("broker connection not found")
        if connection.status is not ConnectionStatus.HEALTHY:
            raise ValueError("broker connection is not healthy")
        context = await self.brokers.get_context(user_id=user_id)
        if context is None or context.connection_id != connection.id:
            raise ValueError("broker connection is not the active user context")
        mandate = profile.adaptive_mandate
        if payload.leverage > mandate.max_leverage:
            raise ValueError("proposal leverage exceeds adaptive mandate")
        portfolio = await self.brokers.get_portfolio_summary(user_id=user_id)
        if portfolio is None or portfolio.connection_id != connection.id:
            raise ValueError("a synchronized portfolio is required")
        maximum_loss = portfolio.total_equity * mandate.max_loss_per_trade_pct
        if payload.estimated_max_loss > maximum_loss:
            raise ValueError("proposal loss exceeds adaptive mandate")
        now = self.clock().astimezone(UTC)
        if payload.expires_at.astimezone(UTC) <= now:
            raise ValueError("proposal expiry must be in the future")

        proposal_id = uuid4()
        proposal_hash = canonical_proposal_hash(
            user_id=user_id,
            proposal_id=proposal_id,
            environment=connection.environment.value,
            payload=payload,
        )
        proposal = TradeProposal(
            **payload.model_dump(),
            id=proposal_id,
            user_id=user_id,
            environment=connection.environment,
            status=ProposalStatus.AVAILABLE,
            proposal_hash=proposal_hash,
            created_at=now,
            updated_at=now,
        )
        stored = await self.proposals.create(proposal)
        if self.notifications is not None:
            try:
                await self.notifications.notify_proposal(stored)
            except Exception:
                logger.exception(
                    "proposal notification failed",
                    extra={"proposal_id": str(stored.id), "user_id": stored.user_id},
                )
        return stored

    async def list(
        self, *, user_id: str, limit: int = 50, offset: int = 0, connection_id: UUID | None = None
    ) -> tuple[TradeProposal, ...]:
        return await self.proposals.list(
            user_id=user_id, limit=limit, offset=offset, connection_id=connection_id
        )

    async def get(self, *, user_id: str, proposal_id: UUID) -> TradeProposal | None:
        return await self.proposals.get(user_id=user_id, proposal_id=proposal_id)

    async def reject(self, *, user_id: str, proposal_id: UUID) -> TradeProposal:
        return await self.proposals.reject(
            user_id=user_id,
            proposal_id=proposal_id,
            now=self.clock().astimezone(UTC),
        )

    async def add_feedback(
        self, *, user_id: str, proposal_id: UUID, payload: ProposalFeedback
    ) -> None:
        proposal = await self._require_proposal(user_id=user_id, proposal_id=proposal_id)
        await self.proposals.add_feedback(
            user_id=user_id,
            proposal_id=proposal_id,
            reason=payload.reason,
            comment=payload.comment,
            now=self.clock().astimezone(UTC),
        )
        if self.memories is not None:
            await self.memories.remember(
                user_id=user_id,
                kind=MemoryKind.EPISODIC,
                key="proposal_feedback",
                value={
                    "proposal_id": str(proposal_id),
                    "strategy_family": proposal.strategy_family,
                    "reason": payload.reason,
                    "comment": payload.comment,
                },
                source=MemorySource.EXPLICIT_FEEDBACK,
                confidence=Decimal("1"),
                evidence_count=1,
            )
            memories = await self.memories.list(user_id=user_id, limit=1_000)
            observations = tuple(
                FeedbackObservation(
                    strategy_family=str(item.value["strategy_family"]),
                    reason=str(item.value["reason"]),
                )
                for item in memories
                if item.kind is MemoryKind.EPISODIC
                and item.key == "proposal_feedback"
                and "strategy_family" in item.value
                and "reason" in item.value
            )
            await self.memories.save_learned_preferences(
                user_id=user_id,
                preferences=PreferenceLearner().infer(observations),
            )

    async def _require_proposal(self, *, user_id: str, proposal_id: UUID) -> TradeProposal:
        proposal = await self.proposals.get(user_id=user_id, proposal_id=proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        return proposal


def canonical_proposal_hash(
    *,
    user_id: str,
    proposal_id: UUID,
    environment: str,
    payload: CreateTradeProposal,
) -> str:
    canonical = {
        "user_id": user_id,
        "proposal_id": str(proposal_id),
        "environment": environment,
        "terms": payload.model_dump(mode="json"),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
