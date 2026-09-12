from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from signalos_backend.market.domain import MarketCategory, TickerSnapshot
from signalos_backend.market.scanner import rank_market
from signalos_backend.market.sessions import SessionName, SessionScheduler, SweepOffset


def test_session_sweeps_are_dst_aware_and_use_all_required_offsets():
    scheduler = SessionScheduler()

    winter = scheduler.sweeps_for_date(SessionName.LONDON, date(2026, 1, 15))
    summer = scheduler.sweeps_for_date(SessionName.LONDON, date(2026, 7, 15))

    assert [event.offset for event in winter] == [
        SweepOffset.PRE_OPEN,
        SweepOffset.OPEN,
        SweepOffset.POST_15,
        SweepOffset.POST_60,
    ]
    assert winter[1].scheduled_at == datetime(2026, 1, 15, 8, tzinfo=UTC)
    assert summer[1].scheduled_at == datetime(2026, 7, 15, 7, tzinfo=UTC)

    new_york_summer = scheduler.sweeps_for_date(SessionName.NEW_YORK, date(2026, 7, 15))
    assert new_york_summer[1].scheduled_at == datetime(2026, 7, 15, 13, 30, tzinfo=UTC)


def test_session_calendar_can_suppress_a_closed_market_activity_window():
    scheduler = SessionScheduler(
        closed_dates={SessionName.NEW_YORK: frozenset({date(2026, 12, 25)})}
    )

    assert scheduler.sweeps_for_date(SessionName.NEW_YORK, date(2026, 12, 25)) == ()
    assert len(scheduler.sweeps_for_date(SessionName.UTC_ROLLOVER, date(2026, 12, 25))) == 4


def test_funding_sweeps_follow_instrument_reported_event_time():
    scheduler = SessionScheduler()
    funding_time = datetime(2026, 8, 14, 16, tzinfo=UTC)

    events = scheduler.funding_sweeps("ETHUSDT", funding_time)

    assert [event.scheduled_at for event in events] == [
        datetime(2026, 8, 14, 15, 45, tzinfo=UTC),
        datetime(2026, 8, 14, 16, tzinfo=UTC),
        datetime(2026, 8, 14, 16, 15, tzinfo=UTC),
        datetime(2026, 8, 14, 17, tzinfo=UTC),
    ]
    assert all(event.symbol == "ETHUSDT" for event in events)


def test_due_sweeps_identify_the_exact_activity_window_without_hardcoded_utc_offsets():
    scheduler = SessionScheduler()
    due = scheduler.due_sweeps(
        datetime(2026, 7, 15, 7, 15, 20, tzinfo=UTC),
        tolerance_seconds=30,
    )

    assert [(event.session, event.offset) for event in due] == [
        (SessionName.LONDON, SweepOffset.POST_15)
    ]


def ticker(index: int, *, turnover: int, change: str) -> TickerSnapshot:
    return TickerSnapshot(
        category=MarketCategory.LINEAR,
        symbol=f"COIN{index}USDT",
        last_price=Decimal("100"),
        bid_price=Decimal("99.9"),
        ask_price=Decimal("100.1"),
        turnover_24h=Decimal(turnover),
        volume_24h=Decimal("1000"),
        price_change_24h=Decimal(change),
        open_interest=Decimal("500"),
        funding_rate=Decimal("0.0001"),
        observed_at=datetime(2026, 8, 14, 12, tzinfo=UTC),
    )


def test_market_ranking_bounds_hot_universe_and_agent_shortlist():
    snapshots = tuple(
        ticker(index, turnover=(index + 1) * 1_000_000, change=str(index / 10_000))
        for index in range(130)
    )

    result = rank_market(snapshots)

    assert len(result.hot_universe) == 100
    assert len(result.agent_shortlist) == 20
    assert result.hot_universe[0].symbol == "COIN129USDT"
    assert result.agent_shortlist == result.hot_universe[:20]
    assert all(candidate.activity_score >= 0 for candidate in result.hot_universe)


def test_market_ranking_rejects_stale_or_invalid_quotes():
    valid = ticker(1, turnover=2_000_000, change="0.01")
    crossed = valid.model_copy(update={"symbol": "BADUSDT", "bid_price": Decimal("101")})
    zero_turnover = valid.model_copy(update={"symbol": "EMPTYUSDT", "turnover_24h": Decimal("0")})

    result = rank_market((crossed, zero_turnover, valid))

    assert [candidate.symbol for candidate in result.hot_universe] == ["COIN1USDT"]
