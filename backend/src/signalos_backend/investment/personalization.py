from __future__ import annotations

from collections import Counter
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from signalos_backend.users.domain import InvestmentProfile


class LearnedPreference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    value: str = Field(min_length=1, max_length=200)
    confidence: Decimal = Field(ge=0, le=1)
    evidence_count: int = Field(ge=1)

    @property
    def is_active(self) -> bool:
        return self.evidence_count >= 5 and self.confidence >= Decimal("0.80")


class UserInvestmentContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: InvestmentProfile
    account_equity: Decimal = Field(gt=0)
    available_capital: Decimal = Field(ge=0)
    correlated_exposure_pct: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    learned_preferences: tuple[LearnedPreference, ...] = ()


class PersonalizedOpportunityInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_family: str
    requested_leverage: Decimal = Field(ge=1)
    estimated_max_loss: Decimal = Field(gt=0)
    required_capital: Decimal = Field(gt=0)


class PersonalizedOpportunityAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    suitable: bool
    allowed_leverage: Decimal = Field(ge=1)
    rank_adjustment: Decimal = Field(ge=-1, le=1)
    reasons: tuple[str, ...]


class PersonalizationPolicy:
    """Apply the adaptive platform mandate before behavior can affect ranking."""

    def assess(
        self,
        context: UserInvestmentContext,
        opportunity: PersonalizedOpportunityInput,
    ) -> PersonalizedOpportunityAssessment:
        hard_failures: list[str] = []
        reasons: list[str] = []
        mandate = context.profile.adaptive_mandate
        maximum_loss = context.account_equity * mandate.max_loss_per_trade_pct
        if opportunity.estimated_max_loss > maximum_loss:
            hard_failures.append("loss_exceeds_adaptive_mandate")
        if opportunity.required_capital > context.available_capital:
            hard_failures.append("insufficient_available_capital")

        allowed_leverage = min(opportunity.requested_leverage, mandate.max_leverage)
        if opportunity.requested_leverage > mandate.max_leverage:
            reasons.append("leverage_capped_by_adaptive_mandate")

        rank_adjustment = Decimal("0")
        if any(
            preference.is_active
            and preference.key == "avoid_strategy_family"
            and preference.value == opportunity.strategy_family
            for preference in context.learned_preferences
        ):
            rank_adjustment -= Decimal("0.20")
            reasons.append("behavioral_preference_deprioritized_strategy")

        return PersonalizedOpportunityAssessment(
            suitable=not hard_failures,
            allowed_leverage=allowed_leverage,
            rank_adjustment=rank_adjustment,
            reasons=tuple((*hard_failures, *reasons)),
        )


class FeedbackObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_family: str = Field(min_length=3, max_length=100)
    reason: str = Field(min_length=3, max_length=100)


class PreferenceLearner:
    """Create cautious ranking preferences; never infer hard risk limits."""

    def infer(self, observations: tuple[FeedbackObservation, ...]) -> tuple[LearnedPreference, ...]:
        if len(observations) < 5:
            return ()
        counts = Counter(
            (observation.strategy_family, observation.reason)
            for observation in observations
            if observation.reason in {"too_short_term", "too_risky", "not_interested"}
        )
        total = Decimal(len(observations))
        preferences: list[LearnedPreference] = []
        for (strategy_family, _reason), count in sorted(counts.items()):
            confidence = Decimal(count) / total
            if count >= 5 and confidence >= Decimal("0.80"):
                preferences.append(
                    LearnedPreference(
                        key="avoid_strategy_family",
                        value=strategy_family,
                        confidence=confidence,
                        evidence_count=count,
                    )
                )
        return tuple(preferences)
