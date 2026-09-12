from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from signalos_backend.brokers.domain import (
    BrokerCredentialPurpose,
    BrokerEnvironment,
    ConnectionStatus,
)
from signalos_backend.brokers.store import (
    BrokerConnectionRecord,
    BrokerContextRecord,
    BrokerCredentialRecord,
)
from signalos_backend.db import Base
from signalos_backend.execution.domain import (
    BrokerExecutionSnapshot,
    BrokerOrder,
    BrokerOrderSnapshot,
    BrokerOrderState,
    BrokerPosition,
    BrokerPositionSnapshot,
    BrokerPositionState,
    ConfirmExecutionActionInput,
    ExecutionAction,
    ExecutionActionReview,
    ExecutionActionState,
    ExecutionActionTerms,
    ExecutionActionType,
    ExecutionConflictError,
    OrderReview,
    OrderTicket,
    PositionPortfolioSnapshot,
    SubmitOrderInput,
)
from signalos_backend.market.domain import MarketCategory
from signalos_backend.proposals.domain import OrderSide, OrderType, ProposalStatus, TradeProposal
from signalos_backend.proposals.store import TradeProposalRecord


class OrderReviewRecord(Base):
    __tablename__ = "order_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("trade_proposals.id", ondelete="CASCADE"), index=True
    )
    proposal_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BrokerOrderRecord(Base):
    __tablename__ = "broker_orders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key"),
        UniqueConstraint("broker_order_link_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("trade_proposals.id", ondelete="RESTRICT"), unique=True
    )
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="RESTRICT"), index=True
    )
    environment: Mapped[str] = mapped_column(String(20), index=True)
    state: Mapped[str] = mapped_column(String(40), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    broker_order_link_id: Mapped[str] = mapped_column(String(36))
    broker_order_id: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(20))
    symbol: Mapped[str | None] = mapped_column(String(40), index=True)
    side: Mapped[str | None] = mapped_column(String(10))
    order_type: Mapped[str | None] = mapped_column(String(20))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    cumulative_executed_quantity: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    leaves_quantity: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    average_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    broker_status: Mapped[str | None] = mapped_column(String(40))
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BrokerExecutionRecord(Base):
    __tablename__ = "broker_executions"
    __table_args__ = (UniqueConstraint("connection_id", "broker_execution_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="RESTRICT"), index=True
    )
    signalos_order_id: Mapped[str | None] = mapped_column(
        ForeignKey("broker_orders.id", ondelete="SET NULL"), index=True
    )
    environment: Mapped[str] = mapped_column(String(20), index=True)
    broker_execution_id: Mapped[str] = mapped_column(String(100))
    broker_order_id: Mapped[str] = mapped_column(String(100), index=True)
    broker_order_link_id: Mapped[str] = mapped_column(String(36), index=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    side: Mapped[str] = mapped_column(String(10))
    price: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    quantity: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    value: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    fee: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BrokerPositionRecord(Base):
    __tablename__ = "broker_positions"
    __table_args__ = (UniqueConstraint("connection_id", "category", "symbol", "position_index"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="RESTRICT"), index=True
    )
    environment: Mapped[str] = mapped_column(String(20), index=True)
    state: Mapped[str] = mapped_column(String(20), index=True)
    category: Mapped[str] = mapped_column(String(20))
    symbol: Mapped[str] = mapped_column(String(40), index=True)
    position_index: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String(10))
    size: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    average_price: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    position_value: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    leverage: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    mark_price: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    liquidation_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    unrealised_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    cumulative_realised_pnl: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    sequence: Mapped[int] = mapped_column(Integer)
    broker_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BrokerReconciliationCheckpointRecord(Base):
    __tablename__ = "broker_reconciliation_checkpoints"

    connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="CASCADE"), primary_key=True
    )
    positions_reconciled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ExecutionActionReviewRecord(Base):
    __tablename__ = "execution_action_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    action_type: Mapped[str] = mapped_column(String(40), index=True)
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    action_hash: Mapped[str] = mapped_column(String(64))
    terms: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ExecutionActionRecord(Base):
    __tablename__ = "execution_actions"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key"),
        UniqueConstraint("review_id"),
        UniqueConstraint("broker_order_link_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_id: Mapped[str] = mapped_column(
        ForeignKey("execution_action_reviews.id", ondelete="RESTRICT")
    )
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    action_type: Mapped[str] = mapped_column(String(40), index=True)
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="RESTRICT"), index=True
    )
    state: Mapped[str] = mapped_column(String(40), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    broker_order_link_id: Mapped[str | None] = mapped_column(String(36))
    broker_order_id: Mapped[str | None] = mapped_column(String(100), index=True)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


@dataclass(frozen=True)
class SubmissionStart:
    order: BrokerOrder
    proposal: TradeProposal
    is_new: bool


@dataclass(frozen=True)
class ActionStart:
    action: ExecutionAction
    terms: ExecutionActionTerms
    is_new: bool


class ExecutionStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def create_review(
        self,
        *,
        user_id: str,
        ticket: OrderTicket,
        now: datetime,
        expires_at: datetime,
    ) -> OrderReview:
        review = OrderReview(
            id=uuid4(),
            user_id=user_id,
            ticket=ticket,
            expires_at=expires_at,
            created_at=now,
        )
        async with self.sessions() as session:
            session.add(
                OrderReviewRecord(
                    id=str(review.id),
                    user_id=user_id,
                    proposal_id=str(ticket.proposal_id),
                    proposal_hash=ticket.proposal_hash,
                    expires_at=expires_at,
                    consumed_at=None,
                    created_at=now,
                )
            )
            await session.commit()
        return review

    async def create_action_review(
        self,
        *,
        user_id: str,
        terms: ExecutionActionTerms,
        action_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> ExecutionActionReview:
        review = ExecutionActionReview(
            id=uuid4(),
            user_id=user_id,
            terms=terms,
            action_hash=action_hash,
            expires_at=expires_at,
            created_at=now,
        )
        async with self.sessions() as session:
            session.add(
                ExecutionActionReviewRecord(
                    id=str(review.id),
                    user_id=user_id,
                    action_type=terms.action_type.value,
                    target_id=str(terms.target_id),
                    action_hash=action_hash,
                    terms=terms.model_dump_json(),
                    expires_at=expires_at,
                    consumed_at=None,
                    created_at=now,
                )
            )
            await session.commit()
        return review

    async def get_action_review(
        self, *, user_id: str, review_id: UUID
    ) -> ExecutionActionReview | None:
        async with self.sessions() as session:
            record = await session.scalar(
                select(ExecutionActionReviewRecord).where(
                    ExecutionActionReviewRecord.id == str(review_id),
                    ExecutionActionReviewRecord.user_id == user_id,
                )
            )
        if record is None:
            return None
        return ExecutionActionReview(
            id=UUID(record.id),
            user_id=record.user_id,
            terms=ExecutionActionTerms.model_validate_json(record.terms),
            action_hash=record.action_hash,
            expires_at=self._as_utc(record.expires_at),
            created_at=self._as_utc(record.created_at),
        )

    async def begin_action(
        self,
        *,
        user_id: str,
        action_type: ExecutionActionType,
        target_id: UUID,
        payload: ConfirmExecutionActionInput,
        now: datetime,
    ) -> ActionStart:
        async with self.sessions() as session:
            # Serialize actions on the same broker target, including different
            # review/idempotency keys from another device or a reopened screen.
            target_model = (
                BrokerOrderRecord
                if action_type is ExecutionActionType.CANCEL_ORDER
                else BrokerPositionRecord
            )
            target = await session.get(target_model, str(target_id), with_for_update=True)
            if target is None or target.user_id != user_id:
                raise KeyError(target_id)
            existing = await session.scalar(
                select(ExecutionActionRecord).where(
                    ExecutionActionRecord.user_id == user_id,
                    ExecutionActionRecord.idempotency_key == payload.idempotency_key,
                )
            )
            if existing is not None:
                if existing.action_type != action_type.value or existing.target_id != str(
                    target_id
                ):
                    raise ExecutionConflictError("idempotency key belongs to another action")
                review_record = await session.get(ExecutionActionReviewRecord, existing.review_id)
                if review_record is None:  # pragma: no cover - foreign key contract
                    raise RuntimeError("execution action review disappeared")
                return ActionStart(
                    action=self._action(existing),
                    terms=ExecutionActionTerms.model_validate_json(review_record.terms),
                    is_new=False,
                )

            pending = await session.scalar(
                select(ExecutionActionRecord.id).where(
                    ExecutionActionRecord.user_id == user_id,
                    ExecutionActionRecord.target_id == str(target_id),
                    ExecutionActionRecord.state.in_((
                        ExecutionActionState.SUBMITTING.value,
                        ExecutionActionState.ACKNOWLEDGED.value,
                        ExecutionActionState.RECONCILIATION_REQUIRED.value,
                    )),
                ).limit(1)
            )
            if pending is not None:
                raise ExecutionConflictError("an action is awaiting broker confirmation")

            review = await session.scalar(
                select(ExecutionActionReviewRecord)
                .where(
                    ExecutionActionReviewRecord.id == str(payload.review_id),
                    ExecutionActionReviewRecord.user_id == user_id,
                    ExecutionActionReviewRecord.action_type == action_type.value,
                    ExecutionActionReviewRecord.target_id == str(target_id),
                )
                .with_for_update()
            )
            if review is None:
                raise KeyError(target_id)
            if review.consumed_at is not None:
                raise ExecutionConflictError("execution action review was already consumed")
            expires_at = self._as_utc(review.expires_at)
            if expires_at <= now:
                raise ExecutionConflictError("execution action review expired")
            if not hmac.compare_digest(review.action_hash, payload.action_hash):
                raise ExecutionConflictError("action hash does not match the reviewed action")
            terms = ExecutionActionTerms.model_validate_json(review.terms)
            action_id = uuid4()
            broker_order_link_id = (
                f"sos-{action_id.hex}"
                if action_type is ExecutionActionType.CLOSE_POSITION
                else None
            )
            record = ExecutionActionRecord(
                id=str(action_id),
                review_id=review.id,
                user_id=user_id,
                action_type=action_type.value,
                target_id=str(target_id),
                connection_id=str(terms.connection_id),
                state=ExecutionActionState.SUBMITTING.value,
                idempotency_key=payload.idempotency_key,
                broker_order_link_id=broker_order_link_id,
                broker_order_id=None,
                error_code=None,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            review.consumed_at = now
            if action_type is ExecutionActionType.CANCEL_ORDER:
                order = await session.get(BrokerOrderRecord, str(target_id), with_for_update=True)
                if order is None or order.user_id != user_id:
                    raise KeyError(target_id)
                order.state = BrokerOrderState.CANCELLING.value
                order.updated_at = now
            await session.commit()
            return ActionStart(action=self._action(record), terms=terms, is_new=True)

    async def mark_action(
        self,
        *,
        action_id: UUID,
        state: ExecutionActionState,
        now: datetime,
        broker_order_id: str | None = None,
        error_code: str | None = None,
    ) -> ExecutionAction:
        async with self.sessions() as session:
            record = await session.get(ExecutionActionRecord, str(action_id), with_for_update=True)
            if record is None:
                raise KeyError(action_id)
            record.state = state.value
            record.broker_order_id = broker_order_id or record.broker_order_id
            record.error_code = error_code[:100] if error_code else None
            record.updated_at = now
            await session.commit()
            return self._action(record)

    async def get_action(self, *, user_id: str, action_id: UUID) -> ExecutionAction | None:
        async with self.sessions() as session:
            record = await session.scalar(
                select(ExecutionActionRecord).where(
                    ExecutionActionRecord.id == str(action_id),
                    ExecutionActionRecord.user_id == user_id,
                )
            )
        return self._action(record) if record is not None else None

    async def get_action_by_idempotency(
        self, *, user_id: str, idempotency_key: str
    ) -> ExecutionAction | None:
        async with self.sessions() as session:
            record = await session.scalar(
                select(ExecutionActionRecord).where(
                    ExecutionActionRecord.user_id == user_id,
                    ExecutionActionRecord.idempotency_key == idempotency_key,
                )
            )
        return self._action(record) if record is not None else None

    async def begin_submission(
        self,
        *,
        user_id: str,
        proposal_id: UUID,
        payload: SubmitOrderInput,
        now: datetime,
    ) -> SubmissionStart:
        async with self.sessions() as session:
            existing = await session.scalar(
                select(BrokerOrderRecord).where(
                    BrokerOrderRecord.user_id == user_id,
                    BrokerOrderRecord.idempotency_key == payload.idempotency_key,
                )
            )
            if existing is not None:
                if existing.proposal_id != str(proposal_id):
                    raise ExecutionConflictError("idempotency key belongs to another proposal")
                proposal_record = await session.get(TradeProposalRecord, str(proposal_id))
                if proposal_record is None or proposal_record.user_id != user_id:
                    raise KeyError(proposal_id)
                return SubmissionStart(
                    order=self._order(existing),
                    proposal=TradeProposal.model_validate_json(proposal_record.payload),
                    is_new=False,
                )

            review = await session.scalar(
                select(OrderReviewRecord)
                .where(
                    OrderReviewRecord.id == str(payload.review_id),
                    OrderReviewRecord.user_id == user_id,
                    OrderReviewRecord.proposal_id == str(proposal_id),
                )
                .with_for_update()
            )
            proposal_record = await session.scalar(
                select(TradeProposalRecord)
                .where(
                    TradeProposalRecord.id == str(proposal_id),
                    TradeProposalRecord.user_id == user_id,
                )
                .with_for_update()
            )
            if review is None or proposal_record is None:
                raise KeyError(proposal_id)
            if review.consumed_at is not None:
                raise ExecutionConflictError("order review was already consumed")
            review_expires_at = review.expires_at
            if review_expires_at.tzinfo is None:
                review_expires_at = review_expires_at.replace(tzinfo=now.tzinfo)
            if review_expires_at <= now:
                raise ExecutionConflictError("order review expired")
            if not hmac.compare_digest(review.proposal_hash, payload.proposal_hash):
                raise ExecutionConflictError("proposal hash does not match the reviewed order")

            proposal = TradeProposal.model_validate_json(proposal_record.payload)
            if proposal.status is not ProposalStatus.AVAILABLE:
                raise ExecutionConflictError(f"proposal cannot be submitted from {proposal.status}")
            if proposal.expires_at <= now:
                raise ExecutionConflictError("proposal expired")
            connection = await session.scalar(
                select(BrokerConnectionRecord)
                .join(
                    BrokerContextRecord,
                    BrokerContextRecord.connection_id == BrokerConnectionRecord.id,
                )
                .where(
                    BrokerConnectionRecord.id == str(proposal.connection_id),
                    BrokerConnectionRecord.user_id == user_id,
                    BrokerConnectionRecord.status == ConnectionStatus.HEALTHY.value,
                    BrokerContextRecord.user_id == user_id,
                )
                .with_for_update()
            )
            if connection is None:
                raise ExecutionConflictError("active broker connection is not healthy")
            credential_exists = await session.scalar(
                select(BrokerCredentialRecord.id).where(
                    BrokerCredentialRecord.connection_id == connection.id,
                    BrokerCredentialRecord.purpose == BrokerCredentialPurpose.BROKER_ACCESS.value,
                )
            )
            if credential_exists is None:
                raise ExecutionConflictError("broker credential is unavailable")

            order_id = uuid4()
            order_link_id = f"sos-{order_id.hex}"
            order_record = BrokerOrderRecord(
                id=str(order_id),
                user_id=user_id,
                proposal_id=str(proposal_id),
                connection_id=connection.id,
                environment=connection.environment,
                state=BrokerOrderState.SUBMITTING.value,
                idempotency_key=payload.idempotency_key,
                broker_order_link_id=order_link_id,
                broker_order_id=None,
                category=proposal.category.value,
                symbol=proposal.symbol,
                side=proposal.side.value,
                order_type=proposal.order_type.value,
                quantity=proposal.quantity,
                cumulative_executed_quantity=Decimal("0"),
                leaves_quantity=proposal.quantity,
                average_price=None,
                broker_status=None,
                last_reconciled_at=None,
                error_code=None,
                created_at=now,
                updated_at=now,
            )
            session.add(order_record)
            review.consumed_at = now
            updated = proposal.model_copy(
                update={"status": ProposalStatus.SUBMITTED, "updated_at": now}
            )
            proposal_record.status = ProposalStatus.SUBMITTED.value
            proposal_record.updated_at = now
            proposal_record.payload = updated.model_dump_json()
            await session.commit()
            return SubmissionStart(order=self._order(order_record), proposal=updated, is_new=True)

    async def get_order(self, *, user_id: str, order_id: UUID) -> BrokerOrder | None:
        async with self.sessions() as session:
            record = await session.scalar(
                select(BrokerOrderRecord).where(
                    BrokerOrderRecord.id == str(order_id),
                    BrokerOrderRecord.user_id == user_id,
                )
            )
            return self._order(record) if record else None

    async def get_order_by_idempotency(
        self, *, user_id: str, idempotency_key: str
    ) -> BrokerOrder | None:
        async with self.sessions() as session:
            record = await session.scalar(
                select(BrokerOrderRecord).where(
                    BrokerOrderRecord.user_id == user_id,
                    BrokerOrderRecord.idempotency_key == idempotency_key,
                )
            )
        return self._order(record) if record is not None else None

    async def list_orders(
        self, *, user_id: str, limit: int = 50, offset: int = 0, proposal_id: UUID | None = None
    ) -> tuple[BrokerOrder, ...]:
        query = select(BrokerOrderRecord).where(BrokerOrderRecord.user_id == user_id)
        if proposal_id is not None:
            query = query.where(BrokerOrderRecord.proposal_id == str(proposal_id))
        async with self.sessions() as session:
            records = (
                await session.scalars(
                    query.order_by(BrokerOrderRecord.created_at.desc()).limit(limit).offset(offset)
                )
            ).all()
        return tuple(self._order(record) for record in records)

    async def list_reconcilable_orders(self, *, connection_id: UUID) -> tuple[BrokerOrder, ...]:
        active = tuple(
            state.value
            for state in (
                BrokerOrderState.SUBMITTING,
                BrokerOrderState.ACKNOWLEDGED,
                BrokerOrderState.PARTIALLY_FILLED,
                BrokerOrderState.CANCELLING,
                BrokerOrderState.SUBMISSION_UNKNOWN,
                BrokerOrderState.RECONCILIATION_REQUIRED,
            )
        )
        async with self.sessions() as session:
            records = (
                await session.scalars(
                    select(BrokerOrderRecord).where(
                        BrokerOrderRecord.connection_id == str(connection_id),
                        BrokerOrderRecord.state.in_(active),
                    )
                )
            ).all()
        return tuple(self._order(record) for record in records)

    async def reconcile_order(
        self,
        *,
        order_id: UUID,
        snapshot: BrokerOrderSnapshot,
        state: BrokerOrderState,
        reconciled_at: datetime,
    ) -> None:
        async with self.sessions() as session:
            record = await session.get(BrokerOrderRecord, str(order_id), with_for_update=True)
            if record is None:
                raise KeyError(order_id)
            record.state = state.value
            record.broker_order_id = snapshot.order_id
            record.category = snapshot.category.value
            record.symbol = snapshot.symbol
            record.side = snapshot.side.value
            record.order_type = snapshot.order_type.value
            record.quantity = snapshot.quantity
            record.cumulative_executed_quantity = snapshot.cumulative_executed_quantity
            record.leaves_quantity = snapshot.leaves_quantity
            record.average_price = snapshot.average_price
            record.broker_status = snapshot.status
            record.last_reconciled_at = reconciled_at
            record.updated_at = reconciled_at
            if state is BrokerOrderState.CANCELLED:
                await self._complete_actions(
                    session,
                    action_type=ExecutionActionType.CANCEL_ORDER,
                    target_id=record.id,
                    completed_at=reconciled_at,
                )
            if state in {BrokerOrderState.CANCELLED, BrokerOrderState.REJECTED} and (
                snapshot.cumulative_executed_quantity == 0
            ):
                await self._archive_proposal(
                    session,
                    proposal_id=record.proposal_id,
                    archived_at=reconciled_at,
                )
            await session.commit()

    async def latest_execution_at(self, *, connection_id: UUID) -> datetime | None:
        async with self.sessions() as session:
            value = await session.scalar(
                select(BrokerExecutionRecord.executed_at)
                .where(BrokerExecutionRecord.connection_id == str(connection_id))
                .order_by(BrokerExecutionRecord.executed_at.desc())
                .limit(1)
            )
        return self._as_utc(value) if value is not None else None

    async def save_executions(
        self,
        *,
        user_id: str,
        connection_id: UUID,
        environment: BrokerEnvironment,
        snapshots: tuple[BrokerExecutionSnapshot, ...],
    ) -> None:
        if not snapshots:
            return
        async with self.sessions() as session:
            existing_ids = set(
                await session.scalars(
                    select(BrokerExecutionRecord.broker_execution_id).where(
                        BrokerExecutionRecord.connection_id == str(connection_id),
                        BrokerExecutionRecord.broker_execution_id.in_(
                            snapshot.execution_id for snapshot in snapshots
                        ),
                    )
                )
            )
            order_links = {
                record.broker_order_link_id: record.id
                for record in (
                    await session.scalars(
                        select(BrokerOrderRecord).where(
                            BrokerOrderRecord.connection_id == str(connection_id),
                            BrokerOrderRecord.broker_order_link_id.in_(
                                snapshot.order_link_id for snapshot in snapshots
                            ),
                        )
                    )
                ).all()
            }
            now = datetime.now(UTC)
            for snapshot in snapshots:
                if snapshot.execution_id in existing_ids:
                    continue
                session.add(
                    BrokerExecutionRecord(
                        id=str(uuid4()),
                        user_id=user_id,
                        connection_id=str(connection_id),
                        signalos_order_id=order_links.get(snapshot.order_link_id),
                        environment=environment.value,
                        broker_execution_id=snapshot.execution_id,
                        broker_order_id=snapshot.order_id,
                        broker_order_link_id=snapshot.order_link_id,
                        symbol=snapshot.symbol,
                        side=snapshot.side.value,
                        price=snapshot.price,
                        quantity=snapshot.quantity,
                        value=snapshot.value,
                        fee=snapshot.fee,
                        executed_at=snapshot.executed_at,
                        created_at=now,
                    )
                )
            await session.commit()

    async def replace_open_positions(
        self,
        *,
        user_id: str,
        connection_id: UUID,
        environment: BrokerEnvironment,
        snapshots: tuple[BrokerPositionSnapshot, ...],
        reconciled_at: datetime,
    ) -> None:
        async with self.sessions() as session:
            records = (
                await session.scalars(
                    select(BrokerPositionRecord)
                    .where(BrokerPositionRecord.connection_id == str(connection_id))
                    .with_for_update()
                )
            ).all()
            by_key = {
                (record.category, record.symbol, record.position_index): record
                for record in records
            }
            seen: set[tuple[str, str, int]] = set()
            for snapshot in snapshots:
                key = (snapshot.category.value, snapshot.symbol, snapshot.position_index)
                seen.add(key)
                record = by_key.get(key)
                if record is None:
                    record = BrokerPositionRecord(
                        id=str(uuid4()),
                        user_id=user_id,
                        connection_id=str(connection_id),
                        environment=environment.value,
                        state=BrokerPositionState.OPEN.value,
                        category=snapshot.category.value,
                        symbol=snapshot.symbol,
                        position_index=snapshot.position_index,
                        side=snapshot.side.value,
                        size=snapshot.size,
                        average_price=snapshot.average_price,
                        position_value=snapshot.position_value,
                        leverage=snapshot.leverage,
                        mark_price=snapshot.mark_price,
                        liquidation_price=snapshot.liquidation_price,
                        take_profit=snapshot.take_profit,
                        stop_loss=snapshot.stop_loss,
                        unrealised_pnl=snapshot.unrealised_pnl,
                        cumulative_realised_pnl=snapshot.cumulative_realised_pnl,
                        sequence=snapshot.sequence,
                        broker_updated_at=snapshot.updated_at,
                        opened_at=snapshot.updated_at,
                        closed_at=None,
                        last_reconciled_at=reconciled_at,
                    )
                    session.add(record)
                else:
                    self._update_position(record, snapshot, reconciled_at)
                    await self._complete_protection_actions(
                        session, record=record, snapshot=snapshot, completed_at=reconciled_at
                    )
            for record in records:
                key = (record.category, record.symbol, record.position_index)
                if record.state == BrokerPositionState.OPEN.value and key not in seen:
                    record.state = BrokerPositionState.CLOSED.value
                    record.size = Decimal("0")
                    record.position_value = Decimal("0")
                    record.unrealised_pnl = Decimal("0")
                    record.closed_at = reconciled_at
                    record.last_reconciled_at = reconciled_at
                    await self._complete_actions(
                        session,
                        action_type=ExecutionActionType.CLOSE_POSITION,
                        target_id=record.id,
                        completed_at=reconciled_at,
                    )
                    await self._archive_symbol_proposals(
                        session,
                        user_id=record.user_id,
                        connection_id=record.connection_id,
                        symbol=record.symbol,
                        archived_at=reconciled_at,
                    )
            checkpoint = await session.get(BrokerReconciliationCheckpointRecord, str(connection_id))
            if checkpoint is None:
                session.add(
                    BrokerReconciliationCheckpointRecord(
                        connection_id=str(connection_id),
                        positions_reconciled_at=reconciled_at,
                    )
                )
            else:
                checkpoint.positions_reconciled_at = reconciled_at
            await session.commit()

    async def list_positions(
        self,
        *,
        user_id: str,
        open_only: bool = True,
        limit: int = 100,
        offset: int = 0,
        connection_id: UUID | None = None,
    ) -> tuple[BrokerPosition, ...]:
        statement = select(BrokerPositionRecord).where(BrokerPositionRecord.user_id == user_id)
        if connection_id is not None:
            statement = statement.where(BrokerPositionRecord.connection_id == str(connection_id))
        if open_only:
            statement = statement.where(
                BrokerPositionRecord.state == BrokerPositionState.OPEN.value
            )
        statement = (
            statement.order_by(BrokerPositionRecord.last_reconciled_at.desc())
            .limit(limit)
            .offset(offset)
        )
        async with self.sessions() as session:
            records = (await session.scalars(statement)).all()
        return tuple(self._position(record) for record in records)

    async def get_position(self, *, user_id: str, position_id: UUID) -> BrokerPosition | None:
        async with self.sessions() as session:
            record = await session.scalar(
                select(BrokerPositionRecord).where(
                    BrokerPositionRecord.id == str(position_id),
                    BrokerPositionRecord.user_id == user_id,
                )
            )
        return self._position(record) if record is not None else None

    async def get_position_portfolio(
        self, *, user_id: str, connection_id: UUID
    ) -> PositionPortfolioSnapshot | None:
        async with self.sessions() as session:
            checkpoint = await session.get(BrokerReconciliationCheckpointRecord, str(connection_id))
            if checkpoint is None:
                return None
            records = (
                await session.scalars(
                    select(BrokerPositionRecord).where(
                        BrokerPositionRecord.user_id == user_id,
                        BrokerPositionRecord.connection_id == str(connection_id),
                        BrokerPositionRecord.state == BrokerPositionState.OPEN.value,
                    )
                )
            ).all()
        return PositionPortfolioSnapshot(
            connection_id=connection_id,
            positions=tuple(self._position(record) for record in records),
            reconciled_at=self._as_utc(checkpoint.positions_reconciled_at),
        )

    async def mark_acknowledged(
        self, *, order_id: UUID, broker_order_id: str, now: datetime
    ) -> BrokerOrder:
        return await self._set_state(
            order_id=order_id,
            state=BrokerOrderState.ACKNOWLEDGED,
            now=now,
            broker_order_id=broker_order_id,
        )

    async def mark_failed(
        self, *, order_id: UUID, state: BrokerOrderState, error_code: str, now: datetime
    ) -> BrokerOrder:
        return await self._set_state(
            order_id=order_id,
            state=state,
            now=now,
            error_code=error_code[:100],
        )

    async def _set_state(
        self,
        *,
        order_id: UUID,
        state: BrokerOrderState,
        now: datetime,
        broker_order_id: str | None = None,
        error_code: str | None = None,
    ) -> BrokerOrder:
        async with self.sessions() as session:
            record = await session.get(BrokerOrderRecord, str(order_id), with_for_update=True)
            if record is None:
                raise KeyError(order_id)
            record.state = state.value
            record.updated_at = now
            record.broker_order_id = broker_order_id or record.broker_order_id
            record.error_code = error_code
            if state is BrokerOrderState.REJECTED:
                await self._archive_proposal(
                    session,
                    proposal_id=record.proposal_id,
                    archived_at=now,
                )
            await session.commit()
            return self._order(record)

    @staticmethod
    def _order(record: BrokerOrderRecord) -> BrokerOrder:
        return BrokerOrder(
            id=UUID(record.id),
            user_id=record.user_id,
            proposal_id=UUID(record.proposal_id),
            connection_id=UUID(record.connection_id),
            environment=BrokerEnvironment(record.environment),
            state=BrokerOrderState(record.state),
            idempotency_key=record.idempotency_key,
            broker_order_link_id=record.broker_order_link_id,
            broker_order_id=record.broker_order_id,
            error_code=record.error_code,
            created_at=ExecutionStore._as_utc(record.created_at),
            updated_at=ExecutionStore._as_utc(record.updated_at),
            category=MarketCategory(record.category) if record.category else None,
            symbol=record.symbol,
            side=OrderSide(record.side) if record.side else None,
            order_type=OrderType(record.order_type) if record.order_type else None,
            quantity=record.quantity or Decimal("0"),
            cumulative_executed_quantity=(record.cumulative_executed_quantity or Decimal("0")),
            leaves_quantity=record.leaves_quantity or Decimal("0"),
            average_price=record.average_price,
            broker_status=record.broker_status,
            last_reconciled_at=(
                ExecutionStore._as_utc(record.last_reconciled_at)
                if record.last_reconciled_at
                else None
            ),
        )

    @staticmethod
    def _update_position(
        record: BrokerPositionRecord,
        snapshot: BrokerPositionSnapshot,
        reconciled_at: datetime,
    ) -> None:
        record.state = BrokerPositionState.OPEN.value
        record.side = snapshot.side.value
        record.size = snapshot.size
        record.average_price = snapshot.average_price
        record.position_value = snapshot.position_value
        record.leverage = snapshot.leverage
        record.mark_price = snapshot.mark_price
        record.liquidation_price = snapshot.liquidation_price
        record.take_profit = snapshot.take_profit
        record.stop_loss = snapshot.stop_loss
        record.unrealised_pnl = snapshot.unrealised_pnl
        record.cumulative_realised_pnl = snapshot.cumulative_realised_pnl
        record.sequence = snapshot.sequence
        record.broker_updated_at = snapshot.updated_at
        record.closed_at = None
        record.last_reconciled_at = reconciled_at

    @staticmethod
    def _position(record: BrokerPositionRecord) -> BrokerPosition:
        return BrokerPosition(
            id=UUID(record.id),
            user_id=record.user_id,
            connection_id=UUID(record.connection_id),
            environment=BrokerEnvironment(record.environment),
            state=BrokerPositionState(record.state),
            category=MarketCategory(record.category),
            symbol=record.symbol,
            position_index=record.position_index,
            side=OrderSide(record.side),
            size=record.size,
            average_price=record.average_price,
            position_value=record.position_value,
            leverage=record.leverage,
            mark_price=record.mark_price,
            liquidation_price=record.liquidation_price,
            take_profit=record.take_profit,
            stop_loss=record.stop_loss,
            unrealised_pnl=record.unrealised_pnl,
            cumulative_realised_pnl=record.cumulative_realised_pnl,
            sequence=record.sequence,
            broker_updated_at=ExecutionStore._as_utc(record.broker_updated_at),
            opened_at=ExecutionStore._as_utc(record.opened_at),
            closed_at=(ExecutionStore._as_utc(record.closed_at) if record.closed_at else None),
            last_reconciled_at=ExecutionStore._as_utc(record.last_reconciled_at),
        )

    @staticmethod
    async def _complete_actions(
        session: AsyncSession,
        *,
        action_type: ExecutionActionType,
        target_id: str,
        completed_at: datetime,
    ) -> None:
        records = (
            await session.scalars(
                select(ExecutionActionRecord).where(
                    ExecutionActionRecord.action_type == action_type.value,
                    ExecutionActionRecord.target_id == target_id,
                    ExecutionActionRecord.state.in_(
                        (
                            ExecutionActionState.ACKNOWLEDGED.value,
                            ExecutionActionState.RECONCILIATION_REQUIRED.value,
                        )
                    ),
                )
            )
        ).all()
        for action in records:
            action.state = ExecutionActionState.COMPLETED.value
            action.updated_at = completed_at

    @staticmethod
    async def _complete_protection_actions(
        session: AsyncSession,
        *,
        record: BrokerPositionRecord,
        snapshot: BrokerPositionSnapshot,
        completed_at: datetime,
    ) -> None:
        actions = (
            await session.scalars(
                select(ExecutionActionRecord).where(
                    ExecutionActionRecord.action_type
                    == ExecutionActionType.UPDATE_PROTECTION.value,
                    ExecutionActionRecord.target_id == record.id,
                    ExecutionActionRecord.state.in_(
                        (
                            ExecutionActionState.ACKNOWLEDGED.value,
                            ExecutionActionState.RECONCILIATION_REQUIRED.value,
                        )
                    ),
                )
            )
        ).all()
        if not actions:
            return
        review_ids = tuple(action.review_id for action in actions)
        reviews = {
            review.id: ExecutionActionTerms.model_validate_json(review.terms)
            for review in (
                await session.scalars(
                    select(ExecutionActionReviewRecord).where(
                        ExecutionActionReviewRecord.id.in_(review_ids)
                    )
                )
            ).all()
        }
        for action in actions:
            terms = reviews[action.review_id]
            if terms.stop_loss == snapshot.stop_loss and terms.take_profit == snapshot.take_profit:
                action.state = ExecutionActionState.COMPLETED.value
                action.updated_at = completed_at

    @staticmethod
    def _action(record: ExecutionActionRecord) -> ExecutionAction:
        return ExecutionAction(
            id=UUID(record.id),
            user_id=record.user_id,
            action_type=ExecutionActionType(record.action_type),
            target_id=UUID(record.target_id),
            connection_id=UUID(record.connection_id),
            state=ExecutionActionState(record.state),
            idempotency_key=record.idempotency_key,
            broker_order_link_id=record.broker_order_link_id,
            broker_order_id=record.broker_order_id,
            error_code=record.error_code,
            created_at=ExecutionStore._as_utc(record.created_at),
            updated_at=ExecutionStore._as_utc(record.updated_at),
        )

    @staticmethod
    async def _archive_proposal(
        session: AsyncSession,
        *,
        proposal_id: str,
        archived_at: datetime,
    ) -> None:
        record = await session.get(TradeProposalRecord, proposal_id, with_for_update=True)
        if record is None or record.status != ProposalStatus.SUBMITTED.value:
            return
        proposal = TradeProposal.model_validate_json(record.payload).model_copy(
            update={"status": ProposalStatus.ARCHIVED, "updated_at": archived_at}
        )
        record.status = ProposalStatus.ARCHIVED.value
        record.updated_at = archived_at
        record.payload = proposal.model_dump_json()

    @staticmethod
    async def _archive_symbol_proposals(
        session: AsyncSession,
        *,
        user_id: str,
        connection_id: str,
        symbol: str,
        archived_at: datetime,
    ) -> None:
        records = (
            await session.scalars(
                select(TradeProposalRecord)
                .where(
                    TradeProposalRecord.user_id == user_id,
                    TradeProposalRecord.connection_id == connection_id,
                    TradeProposalRecord.symbol == symbol,
                    TradeProposalRecord.status == ProposalStatus.SUBMITTED.value,
                )
                .with_for_update()
            )
        ).all()
        for record in records:
            await ExecutionStore._archive_proposal(
                session,
                proposal_id=record.id,
                archived_at=archived_at,
            )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
