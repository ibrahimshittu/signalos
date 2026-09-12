from __future__ import annotations

from decimal import Decimal

from signalos_backend.market.domain import MarketCandidate, MarketScanResult, TickerSnapshot


def rank_market(
    snapshots: tuple[TickerSnapshot, ...],
    *,
    hot_limit: int = 100,
    agent_limit: int = 20,
) -> MarketScanResult:
    """Rank a broad deterministic snapshot before any candidate reaches an LLM."""

    if hot_limit < 1 or agent_limit < 1 or agent_limit > hot_limit:
        raise ValueError("ranking limits must satisfy 1 <= agent_limit <= hot_limit")
    eligible = [
        item
        for item in snapshots
        if item.turnover_24h > 0
        and item.bid_price > 0
        and item.ask_price >= item.bid_price
        and item.last_price > 0
    ]
    if not eligible:
        return MarketScanResult(hot_universe=(), agent_shortlist=())

    by_liquidity = sorted(
        eligible,
        key=lambda item: (item.turnover_24h, abs(item.price_change_24h), item.symbol),
        reverse=True,
    )
    count = Decimal(len(by_liquidity))
    candidates: list[MarketCandidate] = []
    for rank, item in enumerate(by_liquidity):
        liquidity = (count - Decimal(rank)) / count
        movement = min(abs(item.price_change_24h) / Decimal("0.10"), Decimal("1"))
        midpoint = (item.bid_price + item.ask_price) / Decimal("2")
        spread_bps = (
            (item.ask_price - item.bid_price) / midpoint * Decimal("10000")
            if midpoint > 0
            else Decimal("10000")
        )
        spread_quality = max(Decimal("0"), Decimal("1") - spread_bps / Decimal("100"))
        activity = (
            Decimal("0.60") * liquidity
            + Decimal("0.30") * movement
            + Decimal("0.10") * spread_quality
        )
        candidates.append(
            MarketCandidate(
                category=item.category,
                symbol=item.symbol,
                activity_score=activity,
                turnover_24h=item.turnover_24h,
                price_change_24h=item.price_change_24h,
                spread_bps=spread_bps,
                observed_at=item.observed_at,
            )
        )
    ranked = tuple(
        sorted(
            candidates,
            key=lambda item: (item.activity_score, item.turnover_24h, item.symbol),
            reverse=True,
        )[:hot_limit]
    )
    return MarketScanResult(hot_universe=ranked, agent_shortlist=ranked[:agent_limit])
