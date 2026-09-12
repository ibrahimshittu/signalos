from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from signalos_backend.brokers.domain import BrokerConnection


class InvestmentGoal(StrEnum):
    CAPITAL_GROWTH = "capital_growth"
    INCOME = "income"
    CAPITAL_PRESERVATION = "capital_preservation"
    LEARNING = "learning"


class TimeHorizon(StrEnum):
    INTRADAY = "intraday"
    SWING = "swing"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class LiquidityNeed(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ExperienceLevel(StrEnum):
    NONE = "none"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class TradedProduct(StrEnum):
    STOCKS_ETFS = "stocks_etfs"
    CRYPTO_SPOT = "crypto_spot"
    OPTIONS = "options"
    FUTURES = "futures"
    FOREX = "forex"
    MANAGED_PORTFOLIOS = "managed_portfolios"


class DecisionFrequency(StrEnum):
    FIRST_TIME = "first_time"
    FEW_PER_YEAR = "few_per_year"
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    DAILY = "daily"


class DrawdownResponse(StrEnum):
    EXIT = "exit"
    REDUCE = "reduce"
    HOLD = "hold"
    ADD = "add"
    UNSURE = "unsure"


class HoldingPeriod(StrEnum):
    INTRADAY = "intraday"
    MULTI_DAY = "multi_day"
    MULTI_WEEK = "multi_week"
    LONG_TERM = "long_term"


class ExplanationDetail(StrEnum):
    CONCISE = "concise"
    STANDARD = "standard"
    DETAILED = "detailed"


class NotificationFrequency(StrEnum):
    CRITICAL_ONLY = "critical_only"
    OPPORTUNITIES_ONLY = "opportunities_only"
    DAILY_DIGEST = "daily_digest"


class PersonalizedMarket(StrEnum):
    SPOT = "spot"
    PERPETUALS = "linear"


class PersonalizedSession(StrEnum):
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"
    UTC_ROLLOVER = "utc_rollover"
    FUNDING = "funding"


class PersonalizedStrategyFamily(StrEnum):
    TREND = "trend"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    SESSION = "session"
    VOLATILITY = "volatility"
    FUNDING_CARRY = "funding_carry"
    MICROSTRUCTURE = "microstructure"


class InvestmentProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    goals: tuple[InvestmentGoal, ...] = Field(min_length=1, max_length=4)
    # Deprecated planning input retained for older clients. Live synchronized
    # account equity is the only capital value used for proposal sizing.
    intended_capital: Decimal | None = Field(
        default=None, gt=0, max_digits=24, decimal_places=8
    )
    time_horizon: TimeHorizon
    liquidity_need: LiquidityNeed
    investing_experience: ExperienceLevel
    trading_experience: ExperienceLevel
    products_traded: tuple[TradedProduct, ...] = Field(max_length=6)
    decision_frequency: DecisionFrequency
    drawdown_response: DrawdownResponse
    holding_periods: tuple[HoldingPeriod, ...] = Field(min_length=1, max_length=4)
    explanation_detail: ExplanationDetail = ExplanationDetail.STANDARD
    notification_frequency: NotificationFrequency = NotificationFrequency.OPPORTUNITIES_ONLY
    disclosures_accepted: bool

    @field_serializer("intended_capital", when_used="json")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return format(value.normalize(), "f") if value is not None else None


class AdaptiveRiskMandate(BaseModel):
    """Platform-derived risk boundaries; never accepted from a user payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    risk_posture: str
    max_loss_per_trade_pct: Decimal = Field(gt=0, le=Decimal("0.02"))
    max_portfolio_drawdown_pct: Decimal = Field(gt=0, le=Decimal("0.20"))
    max_leverage: Decimal = Field(ge=1, le=20)
    derivatives_eligible: bool
    reasons: tuple[str, ...]
    policy_version: str = "adaptive-mandate-2.0.0"

    @field_serializer(
        "max_loss_per_trade_pct",
        "max_portfolio_drawdown_pct",
        "max_leverage",
        when_used="json",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value.normalize(), "f")


class PersonalizedPreferences(BaseModel):
    """Editable preferences inferred from onboarding; never a risk authorization."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    investor_summary: str = Field(min_length=20, max_length=320)
    priority_objectives: tuple[str, ...] = Field(min_length=1, max_length=4)
    preferred_markets: tuple[PersonalizedMarket, ...] = Field(min_length=1, max_length=2)
    preferred_strategy_families: tuple[PersonalizedStrategyFamily, ...] = Field(
        min_length=1, max_length=5
    )
    preferred_sessions: tuple[PersonalizedSession, ...] = Field(max_length=5)
    holding_periods: tuple[HoldingPeriod, ...] = Field(min_length=1, max_length=4)
    explanation_detail: ExplanationDetail
    notification_frequency: NotificationFrequency
    avoid_conditions: tuple[str, ...] = Field(default_factory=tuple, max_length=6)
    rationale: tuple[str, ...] = Field(min_length=1, max_length=6)


class PersonalizedPreferencesUpdate(BaseModel):
    """User-editable preference fields; generated rationale remains provenance."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    preferred_markets: tuple[PersonalizedMarket, ...] | None = Field(
        default=None, min_length=1, max_length=2
    )
    preferred_strategy_families: tuple[PersonalizedStrategyFamily, ...] | None = Field(
        default=None, min_length=1, max_length=5
    )
    preferred_sessions: tuple[PersonalizedSession, ...] | None = Field(
        default=None, max_length=5
    )
    holding_periods: tuple[HoldingPeriod, ...] | None = Field(
        default=None, min_length=1, max_length=4
    )
    explanation_detail: ExplanationDetail | None = None
    notification_frequency: NotificationFrequency | None = None
    avoid_conditions: tuple[str, ...] | None = Field(default=None, max_length=6)


class PersonalizedInvestmentPolicy(BaseModel):
    """Persisted AI preference layer paired with deterministic safety ceilings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    preferences: PersonalizedPreferences
    safety_mandate: AdaptiveRiskMandate
    source: str
    policy_version: str = "personalization-policy-1.0.0"
    profile_updated_at: datetime
    created_at: datetime
    updated_at: datetime


class InvestmentProfile(InvestmentProfileInput):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    disclosures_accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    adaptive_mandate: AdaptiveRiskMandate


class OnboardingState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    investment_profile_completed: bool
    disclosures_accepted: bool
    broker_account_read_connected: bool
    initial_account_sync_completed: bool
    studio_unlocked: bool
    missing_requirements: tuple[str, ...]
    investment_profile: InvestmentProfile | None = None
    broker_connection: BrokerConnection | None = None
