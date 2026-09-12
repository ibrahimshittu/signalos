from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_status: str
    backtest_passed: bool
    evidence_replicated: bool
    portfolio_risk_passed: bool
    market_observed_at: datetime
    evaluated_at: datetime
    maximum_market_age_seconds: int = Field(default=120, ge=5, le=3_600)

    @model_validator(mode="after")
    def timestamps_are_aware(self) -> GateInput:
        if self.market_observed_at.tzinfo is None or self.evaluated_at.tzinfo is None:
            raise ValueError("gate timestamps must be timezone-aware")
        return self


class MandatoryGateReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    failures: tuple[str, ...]


class MandatoryGateEvaluator:
    """Unskippable application checks that no agent can alter or approve."""

    def evaluate(self, input_: GateInput) -> MandatoryGateReport:
        failures: list[str] = []
        if input_.strategy_status != "approved":
            failures.append("strategy_not_approved")
        if not input_.backtest_passed:
            failures.append("backtest_not_passed")
        if not input_.evidence_replicated:
            failures.append("evidence_not_replicated")
        if not input_.portfolio_risk_passed:
            failures.append("portfolio_risk_rejected")
        age_seconds = (input_.evaluated_at - input_.market_observed_at).total_seconds()
        if age_seconds < 0 or age_seconds > input_.maximum_market_age_seconds:
            failures.append("market_data_stale")
        return MandatoryGateReport(passed=not failures, failures=tuple(failures))
