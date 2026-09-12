from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from signalos_backend.market.domain import Candle, MarketCategory, TickerSnapshot
from signalos_backend.market.signals import DeterministicSignalEngine
from signalos_backend.seeds import build_strategy_registry


def candles(*, step: Decimal) -> tuple[Candle, ...]:
    start = datetime(2026, 8, 14, tzinfo=UTC)
    values: list[Candle] = []
    for index in range(60):
        price = Decimal("100") + step * index
        values.append(
            Candle(
                category=MarketCategory.LINEAR,
                symbol="BTCUSDT",
                interval_minutes=15,
                start_at=start + timedelta(minutes=15 * index),
                end_at=start + timedelta(minutes=15 * (index + 1)),
                open_price=price - Decimal("0.1"),
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal(100 + index),
                turnover=price * Decimal(100 + index),
            )
        )
    return tuple(values)


def ticker(price: Decimal) -> TickerSnapshot:
    return TickerSnapshot(
        category=MarketCategory.LINEAR,
        symbol="BTCUSDT",
        last_price=price,
        bid_price=price - Decimal("0.1"),
        ask_price=price + Decimal("0.1"),
        turnover_24h=Decimal("1000000000"),
        volume_24h=Decimal("100000"),
        price_change_24h=Decimal("0.04"),
        open_interest=Decimal("500000"),
        funding_rate=Decimal("0.0001"),
        observed_at=datetime(2026, 8, 14, 15, tzinfo=UTC),
    )


def test_trend_strategy_builds_price_levels_from_completed_market_data() -> None:
    strategy = build_strategy_registry().get("managed-trend-filter")
    signal = DeterministicSignalEngine().evaluate(
        strategy=strategy,
        candles=candles(step=Decimal("0.2")),
        ticker=ticker(Decimal("111.8")),
    )

    assert signal is not None
    assert signal.side.value == "buy"
    assert signal.stop_loss < signal.entry_price < signal.take_profit
    assert Decimal("1") <= signal.suggested_leverage <= Decimal("20")
    assert signal.reward_to_risk >= Decimal("1.5")
    assert signal.market_observed_at == datetime(2026, 8, 14, 15, tzinfo=UTC)


def test_trend_strategy_returns_no_signal_in_a_flat_market() -> None:
    strategy = build_strategy_registry().get("managed-trend-filter")

    assert (
        DeterministicSignalEngine().evaluate(
            strategy=strategy,
            candles=candles(step=Decimal("0")),
            ticker=ticker(Decimal("100")),
        )
        is None
    )
