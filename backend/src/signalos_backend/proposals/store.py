from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from signalos_backend.db import Base
from signalos_backend.proposals.domain import (
    ProposalConflictError,
    ProposalStatus,
    TradeProposal,
)


class TradeProposalRecord(Base):
    __tablename__ = "trade_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="RESTRICT"), index=True
    )
    environment: Mapped[str] = mapped_column(String(20), index=True)
    strategy_id: Mapped[str] = mapped_column(String(100), index=True)
    strategy_version: Mapped[str] = mapped_column(String(30))
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    proposal_hash: Mapped[str] = mapped_column(String(64), unique=True)
    market_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[str] = mapped_column(Text)


class ProposalFeedbackRecord(Base):
    __tablename__ = "proposal_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("trade_proposals.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    reason: Mapped[str] = mapped_column(String(50), index=True)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ProposalStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def create(self, proposal: TradeProposal) -> TradeProposal:
        async with self.sessions() as session:
            session.add(self._record(proposal))
            await session.commit()
        return proposal

    async def get(self, *, user_id: str, proposal_id: UUID) -> TradeProposal | None:
        async with self.sessions() as session:
            record = await session.scalar(
                select(TradeProposalRecord).where(
                    TradeProposalRecord.id == str(proposal_id),
                    TradeProposalRecord.user_id == user_id,
                )
            )
            return self._domain(record) if record else None

    async def list(
        self, *, user_id: str, limit: int = 50, offset: int = 0, connection_id: UUID | None = None
    ) -> tuple[TradeProposal, ...]:
        statement = select(TradeProposalRecord).where(TradeProposalRecord.user_id == user_id)
        if connection_id is not None:
            statement = statement.where(TradeProposalRecord.connection_id == str(connection_id))
        async with self.sessions() as session:
            records = (
                await session.scalars(
                    statement
                    .order_by(TradeProposalRecord.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            return tuple(self._domain(record) for record in records)

    async def has_active(
        self,
        *,
        user_id: str,
        connection_id: UUID,
        strategy_id: str,
        strategy_version: str,
        symbol: str,
        now: datetime,
    ) -> bool:
        async with self.sessions() as session:
            value = await session.scalar(
                select(TradeProposalRecord.id)
                .where(
                    TradeProposalRecord.user_id == user_id,
                    TradeProposalRecord.connection_id == str(connection_id),
                    TradeProposalRecord.strategy_id == strategy_id,
                    TradeProposalRecord.strategy_version == strategy_version,
                    TradeProposalRecord.symbol == symbol,
                    or_(
                        TradeProposalRecord.status == ProposalStatus.SUBMITTED.value,
                        and_(
                            TradeProposalRecord.status == ProposalStatus.AVAILABLE.value,
                            TradeProposalRecord.expires_at > now,
                        ),
                    ),
                )
                .limit(1)
            )
        return value is not None

    async def reject(self, *, user_id: str, proposal_id: UUID, now: datetime) -> TradeProposal:
        async with self.sessions() as session:
            record = await session.scalar(
                select(TradeProposalRecord)
                .where(
                    TradeProposalRecord.id == str(proposal_id),
                    TradeProposalRecord.user_id == user_id,
                )
                .with_for_update()
            )
            if record is None:
                raise KeyError(proposal_id)
            if record.status != ProposalStatus.AVAILABLE.value:
                raise ProposalConflictError(f"proposal cannot be rejected from {record.status}")
            proposal = self._domain(record).model_copy(
                update={"status": ProposalStatus.REJECTED, "updated_at": now}
            )
            record.status = ProposalStatus.REJECTED.value
            record.updated_at = now
            record.payload = proposal.model_dump_json()
            await session.commit()
            return proposal

    async def add_feedback(
        self,
        *,
        user_id: str,
        proposal_id: UUID,
        reason: str,
        comment: str | None,
        now: datetime,
    ) -> None:
        proposal = await self.get(user_id=user_id, proposal_id=proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        async with self.sessions() as session:
            session.add(
                ProposalFeedbackRecord(
                    id=str(uuid4()),
                    proposal_id=str(proposal_id),
                    user_id=user_id,
                    reason=reason,
                    comment=comment,
                    created_at=now,
                )
            )
            await session.commit()

    @staticmethod
    async def _set_status(
        session: AsyncSession,
        record: TradeProposalRecord,
        status: ProposalStatus,
        now: datetime,
    ) -> None:
        proposal = ProposalStore._domain(record).model_copy(
            update={"status": status, "updated_at": now}
        )
        record.status = status.value
        record.updated_at = now
        record.payload = proposal.model_dump_json()
        await session.flush()

    @staticmethod
    def _record(proposal: TradeProposal) -> TradeProposalRecord:
        return TradeProposalRecord(
            id=str(proposal.id),
            user_id=proposal.user_id,
            connection_id=str(proposal.connection_id),
            environment=proposal.environment.value,
            strategy_id=proposal.strategy_id,
            strategy_version=proposal.strategy_version,
            symbol=proposal.symbol,
            status=proposal.status.value,
            proposal_hash=proposal.proposal_hash,
            market_observed_at=proposal.market_observed_at,
            expires_at=proposal.expires_at,
            created_at=proposal.created_at,
            updated_at=proposal.updated_at,
            payload=proposal.model_dump_json(),
        )

    @staticmethod
    def _domain(record: TradeProposalRecord) -> TradeProposal:
        return TradeProposal.model_validate_json(record.payload)
