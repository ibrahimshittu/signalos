from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from signalos_backend.brokers.domain import (
    BrokerContext,
    BrokerContextSwitch,
    BrokerPolicyError,
    ConnectionStatus,
)
from signalos_backend.brokers.store import (
    BrokerConnectionRecord,
    BrokerContextRecord,
    BrokerCredentialRecord,
)
from signalos_backend.domain import utc_now
from signalos_backend.proposals.domain import ProposalStatus, TradeProposal
from signalos_backend.proposals.store import TradeProposalRecord


class BrokerContextService:
    """Atomically switch user/account context and invalidate account-specific proposals."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.sessions = sessions
        self.clock = clock

    async def switch(self, *, user_id: str, payload: BrokerContextSwitch) -> BrokerContext:
        now = self.clock().astimezone(UTC)
        async with self.sessions() as session:
            connection = await session.scalar(
                select(BrokerConnectionRecord)
                .where(
                    BrokerConnectionRecord.id == str(payload.connection_id),
                    BrokerConnectionRecord.user_id == user_id,
                )
                .with_for_update()
            )
            if connection is None:
                raise KeyError(payload.connection_id)
            if connection.environment != payload.environment.value:
                raise BrokerPolicyError("connection does not belong to the requested environment")
            if (
                connection.status != ConnectionStatus.HEALTHY.value
                or connection.last_synced_at is None
            ):
                raise BrokerPolicyError("connection must be healthy and synced before switching")

            context = await session.get(BrokerContextRecord, user_id, with_for_update=True)
            changed = context is None or context.connection_id != str(payload.connection_id)
            if context is None:
                context = BrokerContextRecord(
                    user_id=user_id,
                    environment=payload.environment.value,
                    connection_id=str(payload.connection_id),
                    switched_at=now,
                )
                session.add(context)
            else:
                context.environment = payload.environment.value
                context.connection_id = str(payload.connection_id)
                context.switched_at = now

            invalidated = (
                await self._invalidate_pending_proposals(session, user_id, now) if changed else 0
            )
            await session.commit()
        return BrokerContext(
            user_id=user_id,
            environment=payload.environment,
            connection_id=payload.connection_id,
            switched_at=now,
            invalidated_proposals=invalidated,
        )

    async def revoke(self, *, user_id: str, connection_id: UUID) -> None:
        now = self.clock().astimezone(UTC)
        connection_key = str(connection_id)
        async with self.sessions() as session:
            connection = await session.scalar(
                select(BrokerConnectionRecord)
                .where(
                    BrokerConnectionRecord.id == connection_key,
                    BrokerConnectionRecord.user_id == user_id,
                )
                .with_for_update()
            )
            if connection is None:
                raise KeyError(connection_id)
            connection.status = ConnectionStatus.REVOKED.value
            connection.last_error_code = "user_revoked"
            connection.updated_at = now
            await session.execute(
                delete(BrokerCredentialRecord).where(
                    BrokerCredentialRecord.connection_id == connection_key
                )
            )
            context = await session.get(BrokerContextRecord, user_id, with_for_update=True)
            if context is not None and context.connection_id == connection_key:
                await session.delete(context)
            await self._invalidate_pending_proposals(
                session,
                user_id,
                now,
                connection_id=connection_key,
            )
            await session.commit()

    @staticmethod
    async def _invalidate_pending_proposals(
        session: AsyncSession,
        user_id: str,
        now: datetime,
        *,
        connection_id: str | None = None,
    ) -> int:
        statement = select(TradeProposalRecord).where(
            TradeProposalRecord.user_id == user_id,
            TradeProposalRecord.status == ProposalStatus.AVAILABLE.value,
        )
        if connection_id is not None:
            statement = statement.where(TradeProposalRecord.connection_id == connection_id)
        records = (await session.scalars(statement.with_for_update())).all()
        if not records:
            return 0
        for record in records:
            proposal = TradeProposal.model_validate_json(record.payload).model_copy(
                update={"status": ProposalStatus.INVALIDATED, "updated_at": now}
            )
            record.status = ProposalStatus.INVALIDATED.value
            record.updated_at = now
            record.payload = proposal.model_dump_json()
        return len(records)
