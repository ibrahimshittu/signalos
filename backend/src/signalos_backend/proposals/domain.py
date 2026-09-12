from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signalos_backend.brokers.domain import BrokerEnvironment
from signalos_backend.investment.gates import MandatoryGateReport
from signalos_backend.market.domain import MarketCategory


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class ProposalStatus(StrEnum):
    AVAILABLE = "available"
    SUBMITTED = "submitted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    ARCHIVED = "archived"


class CreateTradeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    connection_id: UUID
    strategy_id: str = Field(min_length=3, max_length=100)
    strategy_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    strategy_family: str = Field(min_length=3, max_length=100)
    category: MarketCategory
    symbol: str = Field(pattern=r"^[A-Z0-9-]{4,40}$")
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit: Decimal = Field(gt=0)
    leverage: Decimal = Field(ge=1, le=20)
    estimated_fees: Decimal = Field(ge=0)
    estimated_funding: Decimal
    estimated_slippage: Decimal = Field(ge=0)
    estimated_max_loss: Decimal = Field(gt=0)
    required_margin: Decimal | None = Field(default=None, gt=0)
    portfolio_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    position_reconciled_at: datetime | None = None
    market_price: Decimal = Field(gt=0)
    market_observed_at: datetime
    expires_at: datetime
    thesis: str = Field(min_length=20, max_length=4_000)
    opposing_case: str = Field(min_length=20, max_length=4_000)
    why_it_fits: str = Field(min_length=20, max_length=2_000)
    why_reject: str = Field(min_length=20, max_length=2_000)
    gate_report: MandatoryGateReport

    @model_validator(mode="after")
    def validate_order_terms(self) -> CreateTradeProposal:
        if (
            self.market_observed_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or (
                self.position_reconciled_at is not None
                and self.position_reconciled_at.tzinfo is None
            )
        ):
            raise ValueError("proposal timestamps must be timezone-aware")
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for limit orders")
        if self.side is OrderSide.BUY and not self.stop_loss < self.market_price < self.take_profit:
            raise ValueError("buy proposal requires stop_loss < market_price < take_profit")
        if (
            self.side is OrderSide.SELL
            and not self.take_profit < self.market_price < self.stop_loss
        ):
            raise ValueError("sell proposal requires take_profit < market_price < stop_loss")
        return self


class TradeProposal(CreateTradeProposal):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    user_id: str
    environment: BrokerEnvironment
    status: ProposalStatus
    proposal_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    updated_at: datetime


class ProposalFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(pattern=r"^[a-z][a-z0-9_]{2,49}$")
    comment: str | None = Field(default=None, max_length=1_000)


class ProposalConflictError(RuntimeError):
    pass
