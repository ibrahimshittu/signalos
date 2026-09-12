from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from signalos_backend.domain import StrategySpec
from signalos_backend.intelligence.laboratory import ExperimentResult


class ShadowEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    labelled_decisions: int = Field(ge=0)
    regimes: int = Field(ge=0)
    shadow_days: int = Field(ge=0)
    deflated_sharpe_probability: Decimal | None = Field(default=None, ge=0, le=1)
    drawdown_delta_vs_baseline: Decimal
    positive_after_costs: bool
    policy_violations: int = Field(ge=0)
    reserve_violations: int = Field(ge=0)


class PromotionAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    eligible_for_operator_review: bool
    failures: tuple[str, ...]
    operator_approval_still_required: bool = True


def assess_promotion(
    strategy: StrategySpec,
    experiment: ExperimentResult,
    shadow: ShadowEvidence,
) -> PromotionAssessment:
    """Deterministic minimum gate; passing only allows a human review."""
    requirements = strategy.validation_requirements
    failures = list(experiment.failures)
    if not experiment.passed_gates:
        failures.append("experiment_not_passed")
    if (experiment.strategy_id, experiment.strategy_version) != (strategy.id, strategy.version):
        failures.append("experiment_version_mismatch")
    if shadow.labelled_decisions < requirements.min_labelled_decisions:
        failures.append("shadow_decisions_below_minimum")
    if shadow.regimes < requirements.min_regimes:
        failures.append("shadow_regimes_below_minimum")
    if shadow.shadow_days < requirements.min_shadow_days:
        failures.append("shadow_period_below_minimum")
    if shadow.deflated_sharpe_probability is None:
        failures.append("deflated_sharpe_not_computed")
    elif shadow.deflated_sharpe_probability < requirements.deflated_sharpe_probability:
        failures.append("deflated_sharpe_probability_below_minimum")
    if shadow.drawdown_delta_vs_baseline > requirements.max_drawdown_delta_pct:
        failures.append("drawdown_delta_above_limit")
    if requirements.require_positive_after_costs and not shadow.positive_after_costs:
        failures.append("shadow_not_positive_after_costs")
    if shadow.policy_violations:
        failures.append("policy_violations")
    if shadow.reserve_violations:
        failures.append("reserve_violations")
    unique = tuple(dict.fromkeys(failures))
    return PromotionAssessment(
        eligible_for_operator_review=not unique,
        failures=unique,
    )
