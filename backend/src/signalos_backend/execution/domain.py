from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signalos_backend.brokers.domain import BrokerEnvironment
from signalos_backend.market.domain import MarketCategory
from signalos_backend.proposals.domain import OrderSide, OrderType


class BrokerOrderState(StrEnum):
    SUBMITTING = "submitting"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    SUBMISSION_UNKNOWN = "submission_unknown"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class OrderTicket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: UUID
    proposal_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    provider_id: str
    environment: BrokerEnvironment
    category: MarketCategory
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None
    stop_loss: Decimal
    take_profit: Decimal
    leverage: Decimal
    estimated_max_loss: Decimal
    proposal_expires_at: datetime


class OrderReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    user_id: str
    ticket: OrderTicket
    expires_at: datetime
    created_at: datetime


class SubmitOrderInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    review_id: UUID
    proposal_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,100}$")


class BrokerOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    user_id: str
    proposal_id: UUID
    connection_id: UUID
    environment: BrokerEnvironment
    state: BrokerOrderState
    idempotency_key: str
    broker_order_link_id: str = Field(min_length=1, max_length=36)
    broker_order_id: str | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime
    category: MarketCategory | None = None
    symbol: str | None = None
    side: OrderSide | None = None
    order_type: OrderType | None = None
    quantity: Decimal = Field(default=Decimal("0"), ge=0)
    cumulative_executed_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    leaves_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    average_price: Decimal | None = Field(default=None, ge=0)
    broker_status: str | None = None
    last_reconciled_at: datetime | None = None


class BrokerOrderAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: str = Field(min_length=1, max_length=100)
    order_link_id: str = Field(min_length=1, max_length=36)


class BrokerOrderSnapshot(BaseModel):
    """Authoritative order state returned by Bybit reconciliation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: str
    order_link_id: str
    category: MarketCategory
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: str
    quantity: Decimal = Field(ge=0)
    cumulative_executed_quantity: Decimal = Field(ge=0)
    leaves_quantity: Decimal = Field(ge=0)
    average_price: Decimal | None = Field(default=None, ge=0)
    updated_at: datetime


class BrokerExecutionSnapshot(BaseModel):
    """One immutable broker fill. A single order may have multiple fills."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_id: str
    order_id: str
    order_link_id: str
    symbol: str
    side: OrderSide
    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    value: Decimal = Field(ge=0)
    fee: Decimal
    executed_at: datetime


class BrokerPositionSnapshot(BaseModel):
    """Current Bybit derivatives position for one position index."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: MarketCategory
    symbol: str
    position_index: int = Field(ge=0, le=2)
    side: OrderSide
    size: Decimal = Field(gt=0)
    average_price: Decimal = Field(ge=0)
    position_value: Decimal = Field(ge=0)
    leverage: Decimal | None = Field(default=None, ge=1, le=200)
    mark_price: Decimal = Field(ge=0)
    liquidation_price: Decimal | None = Field(default=None, ge=0)
    take_profit: Decimal | None = Field(default=None, ge=0)
    stop_loss: Decimal | None = Field(default=None, ge=0)
    unrealised_pnl: Decimal
    cumulative_realised_pnl: Decimal
    sequence: int
    updated_at: datetime


class BrokerPositionState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class BrokerPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    user_id: str
    connection_id: UUID
    environment: BrokerEnvironment
    state: BrokerPositionState
    category: MarketCategory
    symbol: str
    position_index: int = Field(ge=0, le=2)
    side: OrderSide
    size: Decimal = Field(ge=0)
    average_price: Decimal = Field(ge=0)
    position_value: Decimal = Field(ge=0)
    leverage: Decimal | None = Field(default=None, ge=1, le=200)
    mark_price: Decimal = Field(ge=0)
    liquidation_price: Decimal | None = Field(default=None, ge=0)
    take_profit: Decimal | None = Field(default=None, ge=0)
    stop_loss: Decimal | None = Field(default=None, ge=0)
    unrealised_pnl: Decimal
    cumulative_realised_pnl: Decimal
    sequence: int
    broker_updated_at: datetime
    opened_at: datetime
    closed_at: datetime | None = None
    last_reconciled_at: datetime


class BrokerExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    user_id: str
    connection_id: UUID
    environment: BrokerEnvironment
    broker_execution_id: str
    broker_order_id: str
    broker_order_link_id: str
    symbol: str
    side: OrderSide
    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    value: Decimal = Field(ge=0)
    fee: Decimal
    executed_at: datetime


class PositionPortfolioSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    connection_id: UUID
    positions: tuple[BrokerPosition, ...]
    reconciled_at: datetime


class ExecutionActionType(StrEnum):
    CANCEL_ORDER = "cancel_order"
    CLOSE_POSITION = "close_position"
    UPDATE_PROTECTION = "update_protection"


class ExecutionActionState(StrEnum):
    SUBMITTING = "submitting"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    REJECTED = "rejected"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class UpdateProtectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stop_loss: Decimal | None = Field(default=None, gt=0)
    take_profit: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_a_change(self) -> UpdateProtectionInput:
        if self.stop_loss is None and self.take_profit is None:
            raise ValueError("provide a stop loss or take profit")
        return self


class ExecutionActionTerms(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_type: ExecutionActionType
    target_id: UUID
    connection_id: UUID
    environment: BrokerEnvironment
    category: MarketCategory
    symbol: str
    broker_order_id: str | None = None
    broker_order_link_id: str | None = None
    broker_status: str | None = None
    position_index: int | None = Field(default=None, ge=0, le=2)
    side: OrderSide | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    target_sequence: int | None = None
    mark_price: Decimal | None = Field(default=None, ge=0)
    stop_loss: Decimal | None = Field(default=None, ge=0)
    take_profit: Decimal | None = Field(default=None, ge=0)


class ExecutionActionReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    user_id: str
    terms: ExecutionActionTerms
    action_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: datetime
    created_at: datetime


class ConfirmExecutionActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    review_id: UUID
    action_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,100}$")


class ExecutionAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    user_id: str
    action_type: ExecutionActionType
    target_id: UUID
    connection_id: UUID
    state: ExecutionActionState
    idempotency_key: str
    broker_order_link_id: str | None = None
    broker_order_id: str | None = None
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class ExecutionConflictError(RuntimeError):
    """The reviewed order is stale, mismatched, or no longer eligible."""
