from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from statistics import mean, pstdev

from pydantic import BaseModel, ConfigDict, Field

from signalos_backend.domain import StrategySpec


class ExperimentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    strategy_id: str
    strategy_version: str
    prices: tuple[float, ...] = Field(min_length=60, max_length=1_000_000)
    baseline: tuple[float, ...] | None = None
    bars_per_year: int = Field(default=365, ge=1, le=525_600)


class ExperimentResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    strategy_id: str
    strategy_version: str
    decisions: int
    regimes_observed: int
    gross_return: Decimal
    net_return: Decimal
    baseline_return: Decimal
    annualized_sharpe: Decimal
    max_drawdown: Decimal
    turnover: Decimal
    cost_paid: Decimal
    sensitivity_stable: bool
    reproducibility_hash: str
    passed_gates: bool
    failures: tuple[str, ...]


def _returns(prices: tuple[float, ...]) -> list[float]:
    if any(price <= 0 or not math.isfinite(price) for price in prices):
        raise ValueError("prices must be finite and positive")
    return [(prices[index] / prices[index - 1]) - 1 for index in range(1, len(prices))]


def _max_drawdown(equity: list[float]) -> float:
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    return abs(worst)


def _moving_average(values: tuple[float, ...], index: int, window: int) -> float:
    start = max(0, index - window + 1)
    return mean(values[start : index + 1])


def _position_series(
    strategy: StrategySpec, prices: tuple[float, ...], window_shift: int = 0
) -> list[int]:
    feature = strategy.features[0]
    window = max(2, feature.window + window_shift)
    positions = [0] * len(prices)
    position = 0
    for index in range(window, len(prices)):
        current = prices[index]
        moving_average = _moving_average(prices, index, window)
        if strategy.family.value in {"momentum_trend", "threshold_rebalancing"}:
            position = int(current >= moving_average)
        elif strategy.family.value == "mean_reversion":
            position = int(current <= moving_average)
        else:
            position = 1
        positions[index] = position
    return positions


def _simulate(strategy: StrategySpec, prices: tuple[float, ...], window_shift: int = 0) -> tuple:
    returns = _returns(prices)
    positions = _position_series(strategy, prices, window_shift)
    cost_rate = float(
        (
            strategy.cost_model.fee_bps
            + strategy.cost_model.spread_bps
            + strategy.cost_model.slippage_bps
        )
        / Decimal("10000")
    )
    equity = [1.0]
    net_returns: list[float] = []
    turnover = 0.0
    costs = 0.0
    decisions = 0
    for index, bar_return in enumerate(returns, start=1):
        change = abs(positions[index] - positions[index - 1])
        if change:
            decisions += 1
            turnover += change
            costs += change * cost_rate
        net = positions[index - 1] * bar_return - change * cost_rate
        net_returns.append(net)
        equity.append(equity[-1] * (1 + net))
    return equity, net_returns, turnover, costs, decisions


@dataclass(frozen=True)
class DeterministicExperimentRunner:
    """Compiles the supported DSL into predefined calculations; never executes generated code."""

    def run(self, strategy: StrategySpec, experiment: ExperimentSpec) -> ExperimentResult:
        if (strategy.id, strategy.version) != (
            experiment.strategy_id,
            experiment.strategy_version,
        ):
            raise ValueError("experiment does not match strategy version")
        equity, returns, turnover, costs, decisions = _simulate(strategy, experiment.prices)
        baseline_prices = experiment.baseline or experiment.prices
        baseline_return = baseline_prices[-1] / baseline_prices[0] - 1
        standard_deviation = pstdev(returns) if len(returns) > 1 else 0.0
        sharpe = (
            mean(returns) / standard_deviation * math.sqrt(experiment.bars_per_year)
            if standard_deviation > 0
            else 0.0
        )
        shifted = [_simulate(strategy, experiment.prices, shift)[0][-1] - 1 for shift in (-2, 2)]
        net_return = equity[-1] - 1
        sensitivity_stable = all(abs(result - net_return) <= 0.15 for result in shifted)
        regimes = len(
            {
                "up" if value > 0.005 else "down" if value < -0.005 else "flat"
                for value in _returns(experiment.prices)
            }
        )
        # Price-only research does not replay broker orders, OHLC stops/targets,
        # or the live signal engine. Never mistake these metrics for admission.
        failures = ["execution_replay_not_validated"]
        requirements = strategy.validation_requirements
        if decisions < requirements.min_labelled_decisions:
            failures.append("insufficient_labelled_decisions")
        if regimes < requirements.min_regimes:
            failures.append("insufficient_regime_coverage")
        if requirements.require_positive_after_costs and net_return <= 0:
            failures.append("not_positive_after_costs")
        drawdown = _max_drawdown(equity)
        if drawdown > float(strategy.risk_constraints.max_drawdown_pct):
            failures.append("drawdown_limit_exceeded")
        if not sensitivity_stable:
            failures.append("parameter_sensitivity_unstable")
        from hashlib import sha256

        reproducibility = sha256(
            f"{strategy.model_dump_json()}:{experiment.model_dump_json()}".encode()
        ).hexdigest()
        return ExperimentResult(
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            decisions=decisions,
            regimes_observed=regimes,
            gross_return=Decimal(str((experiment.prices[-1] / experiment.prices[0]) - 1)),
            net_return=Decimal(str(net_return)),
            baseline_return=Decimal(str(baseline_return)),
            annualized_sharpe=Decimal(str(sharpe)),
            max_drawdown=Decimal(str(drawdown)),
            turnover=Decimal(str(turnover)),
            cost_paid=Decimal(str(costs)),
            sensitivity_stable=sensitivity_stable,
            reproducibility_hash=reproducibility,
            passed_gates=not failures,
            failures=tuple(failures),
        )
