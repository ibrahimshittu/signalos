from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SpecialistVerdict(StrEnum):
    SUPPORTIVE = "supportive"
    MIXED = "mixed"
    OPPOSED = "opposed"
    INSUFFICIENT = "insufficient"


class SpecialistAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: SpecialistVerdict
    summary: str = Field(min_length=1, max_length=2_000)
    supporting_factors: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    contrary_factors: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    uncertainties: tuple[str, ...] = Field(default_factory=tuple, max_length=12)


class SessionAssessment(SpecialistAssessment):
    opening_range_context: str = Field(min_length=1, max_length=1_000)


class RegimeAssessment(SpecialistAssessment):
    regime: str = Field(min_length=1, max_length=100)


class StrategyAssessment(SpecialistAssessment):
    strategy_skill_id: str = Field(min_length=1, max_length=100)
    invalidation_conditions: tuple[str, ...] = Field(default_factory=tuple, max_length=12)


class MicrostructureAssessment(SpecialistAssessment):
    execution_quality: str = Field(min_length=1, max_length=500)


class BullCase(SpecialistAssessment):
    thesis: str = Field(min_length=1, max_length=2_000)


class BearCase(SpecialistAssessment):
    thesis_breakers: tuple[str, ...] = Field(min_length=1, max_length=12)


class DecisionAction(StrEnum):
    PROPOSE = "propose"
    WATCH = "watch"
    NO_TRADE = "no_trade"


class InvestmentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_symbol: str = Field(min_length=1, max_length=40)
    action: DecisionAction
    thesis: str = Field(min_length=1, max_length=2_000)
    opposing_case: str = Field(min_length=1, max_length=2_000)
    confidence: Decimal = Field(ge=0, le=1)
    requested_leverage: Decimal = Field(ge=1, le=20)
    required_gate_ids: tuple[str, ...] = (
        "quant_validation",
        "evidence_verification",
        "portfolio_risk",
    )
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=20)


class PortfolioAdvice(BaseModel):
    """User-specific model advice that can only reject or reduce deterministic risk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suitable: bool
    summary: str = Field(min_length=1, max_length=1_000)
    why_it_fits: str = Field(min_length=1, max_length=1_000)
    why_reject: str = Field(min_length=1, max_length=1_000)
    risk_concerns: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    leverage_ceiling: Decimal = Field(ge=1, le=20)
    confidence_multiplier: Decimal = Field(ge=0, le=1)


class PortfolioPositionContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: str
    symbol: str
    side: str
    size: Decimal = Field(gt=0)
    position_value: Decimal = Field(ge=0)
    leverage: Decimal | None = Field(default=None, ge=1)
    average_price: Decimal = Field(ge=0)
    mark_price: Decimal = Field(ge=0)
    unrealised_pnl: Decimal


class PortfolioProfileContext(BaseModel):
    """Identifier-free profile facts allowed into the per-user model context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    goals: tuple[str, ...]
    time_horizon: str
    liquidity_need: str
    investing_experience: str
    trading_experience: str
    products_traded: tuple[str, ...]
    decision_frequency: str
    drawdown_response: str
    holding_periods: tuple[str, ...]
    explanation_detail: str
    risk_posture: str
    max_loss_per_trade_pct: Decimal = Field(gt=0, le=Decimal("0.02"))
    max_leverage: Decimal = Field(ge=1, le=20)
    derivatives_eligible: bool
    personalization_source: str | None = None
    personalization_summary: str | None = None
    preferred_markets: tuple[str, ...] = ()
    preferred_strategy_families: tuple[str, ...] = ()
    preferred_sessions: tuple[str, ...] = ()
    avoid_conditions: tuple[str, ...] = ()
