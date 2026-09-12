from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class StrategyFamily(StrEnum):
    STRATEGIC_ALLOCATION = "strategic_asset_allocation"
    THRESHOLD_REBALANCING = "threshold_rebalancing"
    MOMENTUM_TREND = "momentum_trend"
    MEAN_REVERSION = "mean_reversion"
    FUNDING_BASIS_CARRY = "funding_basis_carry"
    VOLATILITY_DRAWDOWN = "volatility_drawdown"
    MARKET_REGIME = "market_regime"
    EVENT_NEWS = "event_news"
    MACRO_LIQUIDITY = "macro_liquidity"
    ON_CHAIN = "on_chain"
    MICROSTRUCTURE = "microstructure"
    PORTFOLIO_CONSTRUCTION = "portfolio_construction"
    RISK_BEHAVIOUR = "risk_behaviour"


class StrategyStatus(StrEnum):
    DISCOVERED = "discovered"
    QUARANTINED = "quarantined"
    RESEARCH = "research"
    VALIDATED = "validated"
    SHADOW = "shadow"
    PROMOTION_PENDING = "promotion_pending"
    APPROVED = "approved"
    BENCHED = "benched"
    RETIRED = "retired"


class SkillStatus(StrEnum):
    QUARANTINED = "quarantined"
    VALIDATED = "validated"
    APPROVED = "approved"
    RETIRED = "retired"


class SourceTier(IntEnum):
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3
    TIER_4 = 4


class ClaimKind(StrEnum):
    VERIFIED_FACT = "verified_fact"
    CALCULATED_METRIC = "calculated_metric"
    MARKET_CONSENSUS = "market_consensus"
    SIGNALOS_INTERPRETATION = "signalos_interpretation"
    HYPOTHESIS = "hypothesis"
    UNKNOWN = "unknown_or_disputed"


class EvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    DEPENDS_ON = "depends_on"
    APPLIES_TO = "applies_to"


class RiskTier(StrEnum):
    CAUTIOUS = "cautious"
    BALANCED = "balanced"
    ADVENTUROUS = "adventurous"


class FeatureSpec(FrozenModel):
    name: Literal[
        "return",
        "moving_average",
        "volatility",
        "drawdown",
        "rsi",
        "zscore",
        "funding_rate",
        "basis",
        "volume_change",
        "correlation",
        "regime",
    ]
    window: int = Field(default=20, ge=2, le=730)
    source_field: Literal["close", "open", "high", "low", "volume", "funding"] = "close"


class SignalClause(FrozenModel):
    feature: str
    operator: Literal["gt", "gte", "lt", "lte", "crosses_above", "crosses_below"]
    value: float | str


class SignalExpression(FrozenModel):
    mode: Literal["all", "any"] = "all"
    clauses: tuple[SignalClause, ...] = Field(min_length=1, max_length=12)


class EntryExitRules(FrozenModel):
    entry: SignalExpression
    exit: SignalExpression
    cooldown_bars: int = Field(default=1, ge=0, le=365)


class RiskConstraints(FrozenModel):
    max_position_pct: Decimal = Field(default=Decimal("0.55"), gt=0, le=1)
    max_drawdown_pct: Decimal = Field(default=Decimal("0.25"), gt=0, le=1)
    max_turnover_pct_24h: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    reserve_floor_pct: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    long_only: bool = True
    leverage_max: Decimal = Field(default=Decimal("1"), ge=1, le=20)


class CostModel(FrozenModel):
    fee_bps: Decimal = Field(default=Decimal("10"), ge=0, le=500)
    spread_bps: Decimal = Field(default=Decimal("8"), ge=0, le=500)
    slippage_bps: Decimal = Field(default=Decimal("5"), ge=0, le=1000)
    impact_coefficient: Decimal = Field(default=Decimal("0"), ge=0, le=10)


class ValidationRequirements(FrozenModel):
    min_labelled_decisions: int = Field(default=100, ge=20)
    min_regimes: int = Field(default=3, ge=2)
    deflated_sharpe_probability: Decimal = Field(default=Decimal("0.95"), ge=0, le=1)
    max_drawdown_delta_pct: Decimal = Field(default=Decimal("0.02"), ge=0, le=1)
    min_shadow_days: int = Field(default=14, ge=1)
    require_positive_after_costs: bool = True


class StrategySpec(FrozenModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    family: StrategyFamily
    status: StrategyStatus = StrategyStatus.QUARANTINED
    thesis: str = Field(min_length=20, max_length=2_000)
    eligible_universe: tuple[str, ...] = Field(min_length=1, max_length=100)
    holding_horizon: Literal["intraday", "daily", "weekly", "monthly", "strategic"]
    required_data: tuple[str, ...] = Field(min_length=1, max_length=30)
    features: tuple[FeatureSpec, ...] = Field(min_length=1, max_length=20)
    signal_expression: SignalExpression
    parameters: dict[str, Annotated[float, Field(ge=-1_000_000, le=1_000_000)]] = Field(
        default_factory=dict, max_length=30
    )
    entry_and_exit_rules: EntryExitRules
    portfolio_role: str = Field(min_length=3, max_length=300)
    risk_constraints: RiskConstraints
    cost_model: CostModel
    evidence_references: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    known_failure_modes: tuple[str, ...] = Field(min_length=1, max_length=30)
    validation_requirements: ValidationRequirements = Field(default_factory=ValidationRequirements)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("eligible_universe")
    @classmethod
    def normalize_symbols(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(symbol.upper() for symbol in value))

    @model_validator(mode="after")
    def validate_feature_references(self) -> StrategySpec:
        features = {item.name for item in self.features}
        references = {
            clause.feature
            for expression in (
                self.signal_expression,
                self.entry_and_exit_rules.entry,
                self.entry_and_exit_rules.exit,
            )
            for clause in expression.clauses
        }
        unknown = references - features
        if unknown:
            raise ValueError(
                f"signal references unsupported or undeclared features: {sorted(unknown)}"
            )
        return self


class SkillManifest(FrozenModel):
    stable_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(min_length=10, max_length=500)
    routing_triggers: tuple[str, ...] = Field(min_length=1, max_length=30)
    instructions: str = Field(min_length=20, max_length=20_000)
    owned_tools: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    required_skills: tuple[str, ...] = Field(default_factory=tuple, max_length=30)
    evidence_sources: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    reviewer: str = Field(min_length=3, max_length=200)
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    evaluation_suite: str = Field(min_length=3, max_length=200)
    status: SkillStatus = SkillStatus.QUARANTINED

    @model_validator(mode="after")
    def valid_window(self) -> SkillManifest:
        if self.effective_at and self.expires_at and self.expires_at <= self.effective_at:
            raise ValueError("expires_at must follow effective_at")
        return self


class ToolManifest(FrozenModel):
    stable_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,95}$")
    purpose: str = Field(min_length=10, max_length=500)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    access: Literal["read", "write"] = "read"
    required_role: str
    allowed_agents: tuple[str, ...]
    data_sensitivity: Literal["public", "account", "restricted"] = "public"
    freshness_seconds: int = Field(ge=0, le=31_536_000)
    cost_units: int = Field(default=1, ge=0, le=10_000)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=100_000)
    cache_ttl_seconds: int = Field(default=0, ge=0, le=31_536_000)
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    retries: int = Field(default=2, ge=0, le=10)
    approval_required: bool = False
    code_mode: bool = False

    @model_validator(mode="after")
    def enforce_code_mode_safety(self) -> ToolManifest:
        if self.code_mode and (self.access != "read" or self.data_sensitivity != "public"):
            raise ValueError("Code Mode tools must be read-only and public")
        return self


class EvidenceSource(FrozenModel):
    id: UUID = Field(default_factory=uuid4)
    provider: str = Field(min_length=2, max_length=200)
    uri: HttpUrl | str
    title: str = Field(min_length=3, max_length=500)
    tier: SourceTier
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    fingerprint: str = Field(min_length=32, max_length=128)
    content_excerpt: str = Field(default="", max_length=2_000)
    quarantined: bool = True
    verified: bool = False


class EvidenceClaim(FrozenModel):
    id: UUID = Field(default_factory=uuid4)
    text: str = Field(min_length=5, max_length=2_000)
    kind: ClaimKind
    entity_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    source_ids: tuple[UUID, ...] = Field(min_length=1, max_length=50)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    freshness_class: Literal["realtime", "daily", "quarterly", "structural"] = "daily"
    authority_score: Decimal = Field(ge=0, le=1)
    independence_score: Decimal = Field(ge=0, le=1)
    completeness_score: Decimal = Field(ge=0, le=1)
    admitted: bool = False


class EvidenceEdge(FrozenModel):
    from_id: UUID
    to_id: UUID
    relation: EvidenceRelation


class Citation(FrozenModel):
    claim_id: UUID
    source_id: UUID
    label: str


class QuantitativeSnapshot(FrozenModel):
    metrics: dict[str, Decimal | int | str]
    calculation_ids: tuple[str, ...] = ()


class IntelligenceReport(FrozenModel):
    id: UUID = Field(default_factory=uuid4)
    question_id: UUID | None = None
    title: str
    executive_view: str
    what_changed: tuple[str, ...]
    verified_facts: tuple[str, ...]
    quantitative_snapshot: QuantitativeSnapshot
    strategy_interpretations: tuple[str, ...]
    bull_scenario: str
    base_scenario: str
    bear_scenario: str
    portfolio_relevance: str
    drivers: tuple[str, ...]
    risks_and_thesis_breakers: tuple[str, ...]
    monitoring_questions: tuple[str, ...]
    evidence_quality: Decimal = Field(ge=0, le=1)
    source_coverage: Decimal = Field(ge=0, le=1)
    citations: tuple[Citation, ...]
    data_as_of: datetime
    model_versions: dict[str, str]
    skill_versions: dict[str, str]
    tool_versions: dict[str, str]
    prompt_version: str
    evidence_version: str
    policy_version: str
    limitations: tuple[str, ...]
    disputed_claims: tuple[str, ...] = ()
    published_at: datetime = Field(default_factory=utc_now)


class QuestionRequest(FrozenModel):
    question: str = Field(min_length=5, max_length=4_000)
    account_id: str | None = Field(default=None, max_length=200)
    context_entity_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=30)
    mode: Literal["fast", "deep"] = "fast"


class QuestionRun(FrozenModel):
    id: UUID = Field(default_factory=uuid4)
    request: QuestionRequest
    status: Literal["queued", "researching", "verifying", "published", "quarantined", "rejected"]
    report_id: UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RunEvent(FrozenModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    sequence: int = Field(ge=0)
    kind: Literal[
        "queued", "routing", "research", "calculation", "verification", "published", "failed"
    ]
    message: str
    created_at: datetime = Field(default_factory=utc_now)
