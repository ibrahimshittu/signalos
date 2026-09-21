from datetime import UTC, datetime, timedelta
from decimal import Decimal

from signalos_backend.intelligence.laboratory import (
    DeterministicExperimentRunner,
    ExperimentSpec,
    ReplayBar,
)
from signalos_backend.seeds import build_strategy_registry


def test_experiment_is_reproducible_and_cost_aware():
    strategy = build_strategy_registry().get("managed-trend-filter")
    prices = tuple(100 + ((index % 20) - 10) * 0.7 + index * 0.08 for index in range(600))
    spec = ExperimentSpec(
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        prices=prices,
    )
    runner = DeterministicExperimentRunner()
    first = runner.run(strategy, spec)
    second = runner.run(strategy, spec)
    assert first.reproducibility_hash == second.reproducibility_hash
    assert first.cost_paid >= 0
    assert first.net_return <= first.gross_return or first.turnover == 0
    assert first.execution_replay_validated is False
    assert "execution_replay_not_validated" in first.failures


def test_ohlc_experiment_replays_live_signals_stops_targets_and_costs():
    strategy = build_strategy_registry().get("managed-trend-filter")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    closes: list[Decimal] = []
    price = Decimal("100")
    for index in range(240):
        if index < 80:
            price += Decimal("0.35")
        elif index < 150:
            price -= Decimal("0.45")
        else:
            price += Decimal("0.50")
        closes.append(price)
    bars = tuple(
        ReplayBar(
            started_at=start + timedelta(hours=index),
            open_price=close - Decimal("0.1"),
            high_price=close + Decimal("1.5"),
            low_price=close - Decimal("1.5"),
            close_price=close,
            volume=Decimal("1000") + index,
            funding_rate=Decimal("0.0001"),
        )
        for index, close in enumerate(closes)
    )
    spec = ExperimentSpec(
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        bars=bars,
        symbol="BTCUSDT",
        category="linear",
        interval_minutes=60,
        bars_per_year=24 * 365,
    )

    first = DeterministicExperimentRunner().run(strategy, spec)
    second = DeterministicExperimentRunner().run(strategy, spec)

    assert first.execution_replay_validated is True
    assert "execution_replay_not_validated" not in first.failures
    assert first.reproducibility_hash == second.reproducibility_hash
    assert first.turnover > 0
    assert first.cost_paid > 0


def test_execution_replay_uses_stop_when_stop_and_target_share_a_bar():
    strategy = build_strategy_registry().get("managed-trend-filter")
    strategy = strategy.model_copy(
        update={
            "entry_and_exit_rules": strategy.entry_and_exit_rules.model_copy(
                update={"cooldown_bars": 365}
            )
        }
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = []
    for index in range(60):
        close = Decimal("100") + Decimal(index) * Decimal("0.5")
        spread = Decimal("5") if index == 50 else Decimal("0.2")
        bars.append(
            ReplayBar(
                started_at=start + timedelta(hours=index),
                open_price=close - Decimal("0.1"),
                high_price=close + spread,
                low_price=close - spread,
                close_price=close,
                volume=Decimal("1000"),
            )
        )

    result = DeterministicExperimentRunner().run(
        strategy,
        ExperimentSpec(
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            bars=tuple(bars),
        ),
    )

    assert result.execution_replay_validated is True
    assert result.net_return < 0
