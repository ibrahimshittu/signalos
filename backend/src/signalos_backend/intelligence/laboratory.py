from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal
from statistics import mean, pstdev

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signalos_backend.domain import StrategySpec
from signalos_backend.investment.sizing import (
    OpportunitySizingInput,
    OpportunitySizingPolicy,
    SizingRejected,
)
from signalos_backend.market.domain import Candle, MarketCategory, TickerSnapshot
from signalos_backend.market.signals import DeterministicSignalEngine, StrategySignal
from signalos_backend.proposals.domain import OrderSide


class ReplayBar(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    started_at: datetime
    open_price: Decimal = Field(gt=0)
    high_price: Decimal = Field(gt=0)
    low_price: Decimal = Field(gt=0)
    close_price: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)
    funding_rate: Decimal = Decimal("0")

    @model_validator(mode="after")
    def validate_bar(self) -> ReplayBar:
        if self.started_at.tzinfo is None:
            raise ValueError("replay bar timestamp must be timezone-aware")
        if self.low_price > min(self.open_price, self.close_price):
            raise ValueError("replay low is above the candle body")
        if self.high_price < max(self.open_price, self.close_price):
            raise ValueError("replay high is below the candle body")
        return self


class ExperimentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    strategy_id: str
    strategy_version: str
    prices: tuple[float, ...] | None = Field(default=None, min_length=60, max_length=1_000_000)
    bars: tuple[ReplayBar, ...] | None = Field(default=None, min_length=60, max_length=100_000)
    symbol: str = Field(default="BTCUSDT", pattern=r"^[A-Z0-9-]{4,40}$")
    category: MarketCategory = MarketCategory.SPOT
    interval_minutes: int = Field(default=60, ge=1, le=720)
    account_equity: Decimal = Field(default=Decimal("100000"), gt=0)
    available_balance: Decimal = Field(default=Decimal("100000"), ge=0)
    max_loss_per_trade_pct: Decimal = Field(default=Decimal("0.0075"), gt=0, le=Decimal("0.02"))
    mandate_max_leverage: Decimal = Field(default=Decimal("1"), ge=1, le=20)
    broker_max_leverage: Decimal = Field(default=Decimal("100"), ge=1, le=200)
    agent_confidence: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    tick_size: Decimal = Field(default=Decimal("0.01"), gt=0)
    quantity_step: Decimal = Field(default=Decimal("0.001"), gt=0)
    minimum_order_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_notional: Decimal = Field(default=Decimal("0"), ge=0)
    baseline: tuple[float, ...] | None = None
    bars_per_year: int = Field(default=365, ge=1, le=525_600)

    @model_validator(mode="after")
    def require_one_market_series(self) -> ExperimentSpec:
        if (self.prices is None) == (self.bars is None):
            raise ValueError("provide exactly one of prices or bars")
        if self.bars is not None and any(
            current.started_at <= previous.started_at
            for previous, current in zip(self.bars, self.bars[1:], strict=False)
        ):
            raise ValueError("replay bars must be in strictly increasing time order")
        return self


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
    execution_replay_validated: bool = False
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


@dataclass
class _ReplayPosition:
    side: OrderSide
    reference_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    exposure: Decimal


def _rounded_levels(
    signal: StrategySignal, tick_size: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    def floor(value: Decimal) -> Decimal:
        return (value / tick_size).to_integral_value(rounding=ROUND_DOWN) * tick_size

    def ceiling(value: Decimal) -> Decimal:
        return (value / tick_size).to_integral_value(rounding=ROUND_CEILING) * tick_size

    entry = floor(signal.entry_price)
    if signal.side is OrderSide.BUY:
        return entry, floor(signal.stop_loss), floor(signal.take_profit)
    return entry, ceiling(signal.stop_loss), ceiling(signal.take_profit)


def _replay(
    strategy: StrategySpec,
    experiment: ExperimentSpec,
    window_shift: int = 0,
) -> tuple[list[float], list[float], float, float, int, float]:
    if experiment.bars is None:  # pragma: no cover - caller contract
        raise ValueError("OHLC bars are required for execution replay")
    engine = DeterministicSignalEngine()
    sizing_policy = OpportunitySizingPolicy()
    candles: list[Candle] = []
    pending: StrategySignal | None = None
    position: _ReplayPosition | None = None
    cooldown_until = 0
    equity = [1.0]
    gross_equity = 1.0
    net_returns: list[float] = []
    turnover = Decimal("0")
    costs = Decimal("0")
    decisions = 0
    cost_rate = (
        strategy.cost_model.fee_bps
        + strategy.cost_model.spread_bps
        + strategy.cost_model.slippage_bps
    ) / Decimal("10000")

    for index, bar in enumerate(experiment.bars):
        bar_cost = Decimal("0")
        if pending is not None and position is None:
            entry, stop_loss, take_profit = _rounded_levels(pending, experiment.tick_size)
            fill_price: Decimal | None = None
            if pending.side is OrderSide.BUY and bar.low_price <= entry:
                fill_price = min(bar.open_price, entry)
            elif pending.side is OrderSide.SELL and bar.high_price >= entry:
                fill_price = max(bar.open_price, entry)
            if fill_price is not None:
                try:
                    sizing = sizing_policy.size(
                        OpportunitySizingInput(
                            category=experiment.category,
                            side=pending.side,
                            entry_price=entry,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            account_equity=experiment.account_equity,
                            available_balance=experiment.available_balance,
                            strategy_max_position_pct=(
                                strategy.risk_constraints.max_position_pct
                            ),
                            reserve_floor_pct=strategy.risk_constraints.reserve_floor_pct,
                            max_loss_per_trade_pct=experiment.max_loss_per_trade_pct,
                            mandate_max_leverage=experiment.mandate_max_leverage,
                            broker_max_leverage=experiment.broker_max_leverage,
                            agent_requested_leverage=pending.suggested_leverage,
                            agent_confidence=experiment.agent_confidence,
                            quantity_step=experiment.quantity_step,
                            minimum_order_quantity=experiment.minimum_order_quantity,
                            minimum_notional=experiment.minimum_notional,
                            round_trip_cost_bps=(
                                strategy.cost_model.fee_bps
                                + strategy.cost_model.spread_bps
                                + strategy.cost_model.slippage_bps
                                + abs(bar.funding_rate) * Decimal("10000")
                            ),
                        )
                    )
                except (SizingRejected, ValueError):
                    sizing = None
                if sizing is not None:
                    exposure = sizing.notional / experiment.account_equity
                    position = _ReplayPosition(
                        side=pending.side,
                        reference_price=fill_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        exposure=exposure,
                    )
                    bar_cost += exposure * cost_rate
                    turnover += exposure
            pending = None

        price_return = Decimal("0")
        funding_cost = Decimal("0")
        if position is not None:
            exit_price: Decimal | None = None
            if position.side is OrderSide.BUY:
                if bar.low_price <= position.stop_loss:
                    exit_price = min(bar.open_price, position.stop_loss)
                elif bar.high_price >= position.take_profit:
                    exit_price = position.take_profit
                direction = Decimal("1")
            else:
                if bar.high_price >= position.stop_loss:
                    exit_price = max(bar.open_price, position.stop_loss)
                elif bar.low_price <= position.take_profit:
                    exit_price = position.take_profit
                direction = Decimal("-1")
            mark_price = exit_price or bar.close_price
            price_return = (
                direction
                * ((mark_price / position.reference_price) - Decimal("1"))
                * position.exposure
            )
            if experiment.category is MarketCategory.LINEAR:
                funding_cost = abs(bar.funding_rate) * position.exposure
            if exit_price is not None or index == len(experiment.bars) - 1:
                bar_cost += position.exposure * cost_rate
                turnover += position.exposure
                position = None
                cooldown_until = index + strategy.entry_and_exit_rules.cooldown_bars + 1
            else:
                position.reference_price = bar.close_price

        net = price_return - funding_cost - bar_cost
        net_float = max(float(net), -0.999999)
        net_returns.append(net_float)
        equity.append(equity[-1] * (1 + net_float))
        gross_equity *= 1 + max(float(price_return), -0.999999)
        costs += bar_cost + funding_cost

        candle = Candle(
            category=experiment.category,
            symbol=experiment.symbol,
            interval_minutes=experiment.interval_minutes,
            start_at=bar.started_at.astimezone(UTC),
            end_at=bar.started_at.astimezone(UTC)
            + timedelta(minutes=experiment.interval_minutes),
            open_price=bar.open_price,
            high_price=bar.high_price,
            low_price=bar.low_price,
            close_price=bar.close_price,
            volume=bar.volume,
            turnover=bar.volume * bar.close_price,
        )
        candles.append(candle)
        if position is None and pending is None and index >= cooldown_until and len(candles) >= 50:
            decisions += 1
            pending = engine.evaluate(
                strategy=strategy,
                candles=tuple(candles),
                ticker=TickerSnapshot(
                    category=experiment.category,
                    symbol=experiment.symbol,
                    last_price=bar.close_price,
                    bid_price=bar.close_price,
                    ask_price=bar.close_price,
                    turnover_24h=bar.volume * bar.close_price,
                    volume_24h=bar.volume,
                    price_change_24h=Decimal("0"),
                    funding_rate=bar.funding_rate,
                    observed_at=candle.end_at,
                ),
                window_shift=window_shift,
            )
    return (
        equity,
        net_returns,
        float(turnover),
        float(costs),
        decisions,
        gross_equity - 1,
    )


@dataclass(frozen=True)
class DeterministicExperimentRunner:
    """Compiles the supported DSL into predefined calculations; never executes generated code."""

    def run(self, strategy: StrategySpec, experiment: ExperimentSpec) -> ExperimentResult:
        if (strategy.id, strategy.version) != (
            experiment.strategy_id,
            experiment.strategy_version,
        ):
            raise ValueError("experiment does not match strategy version")
        execution_replay_validated = experiment.bars is not None
        prices = (
            tuple(float(bar.close_price) for bar in experiment.bars)
            if experiment.bars is not None
            else experiment.prices
        )
        if prices is None:  # pragma: no cover - model validation contract
            raise ValueError("market series is required")
        if execution_replay_validated:
            equity, returns, turnover, costs, decisions, gross_return = _replay(
                strategy, experiment
            )
        else:
            equity, returns, turnover, costs, decisions = _simulate(strategy, prices)
            gross_return = (prices[-1] / prices[0]) - 1
        baseline_prices = experiment.baseline or prices
        baseline_return = baseline_prices[-1] / baseline_prices[0] - 1
        standard_deviation = pstdev(returns) if len(returns) > 1 else 0.0
        sharpe = (
            mean(returns) / standard_deviation * math.sqrt(experiment.bars_per_year)
            if standard_deviation > 0
            else 0.0
        )
        shifted = [
            (
                _replay(strategy, experiment, shift)[0][-1] - 1
                if execution_replay_validated
                else _simulate(strategy, prices, shift)[0][-1] - 1
            )
            for shift in (-2, 2)
        ]
        net_return = equity[-1] - 1
        sensitivity_stable = all(abs(result - net_return) <= 0.15 for result in shifted)
        regimes = len(
            {
                "up" if value > 0.005 else "down" if value < -0.005 else "flat"
                for value in _returns(prices)
            }
        )
        failures = [] if execution_replay_validated else ["execution_replay_not_validated"]
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
            gross_return=Decimal(str(gross_return)),
            net_return=Decimal(str(net_return)),
            baseline_return=Decimal(str(baseline_return)),
            annualized_sharpe=Decimal(str(sharpe)),
            max_drawdown=Decimal(str(drawdown)),
            turnover=Decimal(str(turnover)),
            cost_paid=Decimal(str(costs)),
            sensitivity_stable=sensitivity_stable,
            execution_replay_validated=execution_replay_validated,
            reproducibility_hash=reproducibility,
            passed_gates=not failures,
            failures=tuple(failures),
        )
