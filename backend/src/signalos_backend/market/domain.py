from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signalos_backend.brokers.domain import BrokerEnvironment


class MarketCategory(StrEnum):
    SPOT = "spot"
    LINEAR = "linear"


class MarketReviewStatus(StrEnum):
    MODEL_UNAVAILABLE = "model_unavailable"
    MARKET_DATA_UNAVAILABLE = "market_data_unavailable"
    NO_APPROVED_STRATEGY = "no_approved_strategy"
    NO_STRATEGY_MATCH = "no_strategy_match"
    EVIDENCE_GATE_REJECTED = "evidence_gate_rejected"
    NO_VALID_SIGNAL = "no_valid_signal"
    AI_NO_TRADE = "ai_no_trade"
    PASSED_MARKET_CHECKS = "passed_market_checks"


class MarketAnalysisRequestStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Instrument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: MarketCategory
    symbol: str = Field(pattern=r"^[A-Z0-9-]{4,40}$")
    base_coin: str
    quote_coin: str
    status: str
    tick_size: Decimal = Field(gt=0)
    quantity_step: Decimal = Field(gt=0)
    minimum_order_quantity: Decimal = Field(ge=0)
    minimum_notional: Decimal = Field(ge=0)
    funding_interval_minutes: int | None = Field(default=None, ge=1, le=24 * 60)


class TickerSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: MarketCategory
    symbol: str = Field(pattern=r"^[A-Z0-9-]{4,40}$")
    last_price: Decimal = Field(gt=0)
    bid_price: Decimal = Field(ge=0)
    ask_price: Decimal = Field(ge=0)
    turnover_24h: Decimal = Field(ge=0)
    volume_24h: Decimal = Field(ge=0)
    price_change_24h: Decimal
    open_interest: Decimal | None = Field(default=None, ge=0)
    funding_rate: Decimal | None = None
    next_funding_at: datetime | None = None
    observed_at: datetime

    @model_validator(mode="after")
    def timestamp_is_aware(self) -> TickerSnapshot:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.next_funding_at is not None and self.next_funding_at.tzinfo is None:
            raise ValueError("next_funding_at must be timezone-aware")
        return self


class Candle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: MarketCategory
    symbol: str = Field(pattern=r"^[A-Z0-9-]{4,40}$")
    interval_minutes: int = Field(ge=1, le=720)
    start_at: datetime
    end_at: datetime
    open_price: Decimal = Field(gt=0)
    high_price: Decimal = Field(gt=0)
    low_price: Decimal = Field(gt=0)
    close_price: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)
    turnover: Decimal = Field(ge=0)
    closed: bool = True

    @model_validator(mode="after")
    def validate_candle(self) -> Candle:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("candle timestamps must be timezone-aware")
        if self.end_at <= self.start_at:
            raise ValueError("candle end_at must follow start_at")
        if self.low_price > min(self.open_price, self.close_price):
            raise ValueError("candle low is above its body")
        if self.high_price < max(self.open_price, self.close_price):
            raise ValueError("candle high is below its body")
        return self


class MarketCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: MarketCategory
    symbol: str
    activity_score: Decimal = Field(ge=0, le=1)
    turnover_24h: Decimal
    price_change_24h: Decimal
    spread_bps: Decimal = Field(ge=0)
    observed_at: datetime


class MarketScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hot_universe: tuple[MarketCandidate, ...]
    agent_shortlist: tuple[MarketCandidate, ...]


class MarketScan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    environment: BrokerEnvironment
    source_count: int = Field(ge=0)
    observed_at: datetime
    created_at: datetime
    result: MarketScanResult

    @model_validator(mode="after")
    def timestamps_are_aware(self) -> MarketScan:
        if self.observed_at.tzinfo is None or self.created_at.tzinfo is None:
            raise ValueError("market scan timestamps must be timezone-aware")
        return self


class PortfolioReviewOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=280)
    evaluated_at: datetime


class MarketReviewCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: MarketCategory
    symbol: str = Field(pattern=r"^[A-Z0-9-]{4,40}$")
    rank: int = Field(ge=1)
    status: MarketReviewStatus
    reason: str = Field(min_length=1, max_length=280)
    strategy_id: str | None = Field(default=None, max_length=100)
    portfolio_review: PortfolioReviewOutcome | None = None


class MarketReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scan_id: str
    environment: BrokerEnvironment
    analyzed_at: datetime
    approved_strategies: int = Field(ge=0)
    candidates_considered: int = Field(ge=0)
    strategy_matches: int = Field(ge=0)
    signals_found: int = Field(ge=0)
    analysis_completed: int = Field(ge=0)
    no_trade_decisions: int = Field(ge=0)
    proposals_created: int = Field(ge=0)
    duplicates_skipped: int = Field(ge=0)
    gate_rejections: int = Field(ge=0)
    model_available: bool
    candidates: tuple[MarketReviewCandidate, ...] = Field(max_length=5)

    @model_validator(mode="after")
    def analyzed_timestamp_is_aware(self) -> MarketReview:
        if self.analyzed_at.tzinfo is None:
            raise ValueError("analyzed_at must be timezone-aware")
        return self


class MarketAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    environment: BrokerEnvironment
    status: MarketAnalysisRequestStatus
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    scan_id: str | None = None
    error_code: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def timestamps_are_aware(self) -> MarketAnalysisRequest:
        timestamps = (self.requested_at, self.started_at, self.completed_at)
        if any(value is not None and value.tzinfo is None for value in timestamps):
            raise ValueError("market analysis request timestamps must be timezone-aware")
        return self
