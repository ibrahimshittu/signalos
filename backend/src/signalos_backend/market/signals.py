from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from signalos_backend.domain import StrategyFamily, StrategySpec
from signalos_backend.market.domain import Candle, MarketCategory, TickerSnapshot
from signalos_backend.proposals.domain import OrderSide


class StrategySignal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: str
    strategy_version: str
    category: MarketCategory
    symbol: str
    side: OrderSide
    entry_price: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit: Decimal = Field(gt=0)
    suggested_leverage: Decimal = Field(ge=1, le=20)
    reward_to_risk: Decimal = Field(gt=0)
    trend_strength: Decimal = Field(ge=0)
    realized_volatility: Decimal = Field(ge=0)
    volume_ratio: Decimal = Field(ge=0)
    market_observed_at: datetime


class DeterministicSignalEngine:
    """Translate completed candles into version-bound terms without generated code."""

    def evaluate(
        self,
        *,
        strategy: StrategySpec,
        candles: tuple[Candle, ...],
        ticker: TickerSnapshot,
    ) -> StrategySignal | None:
        if strategy.family is not StrategyFamily.MOMENTUM_TREND or len(candles) < 50:
            return None
        if any(
            candle.symbol != ticker.symbol
            or candle.category is not ticker.category
            or not candle.closed
            for candle in candles
        ):
            raise ValueError("signal candles must be closed and match the ticker")

        closes = tuple(candle.close_price for candle in candles)
        fast = sum(closes[-20:]) / Decimal("20")
        slow = sum(closes[-50:]) / Decimal("50")
        trend_strength = abs(fast - slow) / ticker.last_price
        if trend_strength < Decimal("0.002"):
            return None
        if ticker.last_price > fast > slow:
            side = OrderSide.BUY
        elif ticker.last_price < fast < slow and not strategy.risk_constraints.long_only:
            side = OrderSide.SELL
        else:
            return None

        average_true_range = self._average_true_range(candles[-15:])
        stop_distance = max(
            average_true_range * Decimal("1.5"),
            ticker.last_price * Decimal("0.005"),
        )
        reward_to_risk = Decimal("1.5") + min(Decimal("1.5"), trend_strength * Decimal("50"))
        if side is OrderSide.BUY:
            stop_loss = ticker.last_price - stop_distance
            take_profit = ticker.last_price + stop_distance * reward_to_risk
        else:
            stop_loss = ticker.last_price + stop_distance
            take_profit = ticker.last_price - stop_distance * reward_to_risk
        if take_profit <= 0:
            return None

        stop_pct = stop_distance / ticker.last_price
        volatility_leverage = max(Decimal("1"), Decimal("0.10") / stop_pct)
        suggested_leverage = min(
            Decimal("20"), strategy.risk_constraints.leverage_max, volatility_leverage
        )
        volumes = tuple(candle.volume for candle in candles[-20:])
        average_volume = sum(volumes) / Decimal(len(volumes))
        volume_ratio = candles[-1].volume / average_volume if average_volume > 0 else Decimal("0")

        return StrategySignal(
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            category=ticker.category,
            symbol=ticker.symbol,
            side=side,
            entry_price=ticker.last_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            suggested_leverage=suggested_leverage,
            reward_to_risk=reward_to_risk,
            trend_strength=trend_strength,
            realized_volatility=average_true_range / ticker.last_price,
            volume_ratio=volume_ratio,
            market_observed_at=ticker.observed_at,
        )

    @staticmethod
    def _average_true_range(candles: tuple[Candle, ...]) -> Decimal:
        ranges: list[Decimal] = []
        for index, candle in enumerate(candles):
            previous_close = candles[index - 1].close_price if index else candle.open_price
            ranges.append(
                max(
                    candle.high_price - candle.low_price,
                    abs(candle.high_price - previous_close),
                    abs(candle.low_price - previous_close),
                )
            )
        return sum(ranges) / Decimal(len(ranges))
