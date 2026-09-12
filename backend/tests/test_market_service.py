from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event

from signalos_backend.brokers.domain import BrokerEnvironment
from signalos_backend.db import IntelligenceStore, build_engine
from signalos_backend.market.domain import (
    Instrument,
    MarketAnalysisRequestStatus,
    MarketCategory,
    TickerSnapshot,
)
from signalos_backend.market.service import MarketService, StaleMarketDataError
from signalos_backend.market.store import MarketStore


class FakeMarketGateway:
    def __init__(
        self,
        *,
        instruments: tuple[Instrument, ...],
        tickers: tuple[TickerSnapshot, ...],
    ) -> None:
        self.instruments = instruments
        self.tickers = tickers
        self.instrument_requests = 0

    async def get_instruments(self, *, environment: BrokerEnvironment) -> tuple[Instrument, ...]:
        del environment
        self.instrument_requests += 1
        return self.instruments

    async def get_tickers(self, *, environment: BrokerEnvironment) -> tuple[TickerSnapshot, ...]:
        del environment
        return self.tickers


def instrument(category: MarketCategory, symbol: str) -> Instrument:
    return Instrument(
        category=category,
        symbol=symbol,
        base_coin=symbol.removesuffix("USDT"),
        quote_coin="USDT",
        status="Trading",
        tick_size=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
        minimum_order_quantity=Decimal("0.001"),
        minimum_notional=Decimal("5"),
        funding_interval_minutes=480 if category is MarketCategory.LINEAR else None,
    )


def ticker(
    category: MarketCategory,
    symbol: str,
    *,
    observed_at: datetime,
    turnover: str,
) -> TickerSnapshot:
    return TickerSnapshot(
        category=category,
        symbol=symbol,
        last_price=Decimal("100"),
        bid_price=Decimal("99.9"),
        ask_price=Decimal("100.1"),
        turnover_24h=Decimal(turnover),
        volume_24h=Decimal("1000"),
        price_change_24h=Decimal("0.02"),
        observed_at=observed_at,
    )


@pytest.mark.asyncio
async def test_scan_refreshes_universe_filters_and_persists_by_environment(tmp_path):
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    instruments = (
        instrument(MarketCategory.SPOT, "BTCUSDT"),
        instrument(MarketCategory.LINEAR, "ETHUSDT"),
    )
    gateway = FakeMarketGateway(
        instruments=instruments,
        tickers=(
            ticker(MarketCategory.SPOT, "BTCUSDT", observed_at=now, turnover="1000000"),
            ticker(MarketCategory.LINEAR, "ETHUSDT", observed_at=now, turnover="2000000"),
            ticker(MarketCategory.SPOT, "USDCUSDT", observed_at=now, turnover="9000000"),
        ),
    )
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'market.db'}")
    intelligence = IntelligenceStore(engine)
    await intelligence.create_schema()
    store = MarketStore(intelligence.sessions)
    clock_now = [now]
    service = MarketService(store=store, gateway=gateway, clock=lambda: clock_now[0])

    scan = await service.run_scan(environment=BrokerEnvironment.MAINNET)
    clock_now[0] += timedelta(seconds=1)
    second = await service.run_scan(environment=BrokerEnvironment.MAINNET)

    assert scan.source_count == 2
    assert [item.symbol for item in scan.result.hot_universe] == ["ETHUSDT", "BTCUSDT"]
    assert gateway.instrument_requests == 1
    assert await service.latest_scan(environment=BrokerEnvironment.MAINNET) == second
    assert await service.latest_scan(environment=BrokerEnvironment.TESTNET) is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_scan_validates_freshness_after_a_slow_universe_refresh(tmp_path):
    scan_started_at = datetime(2026, 8, 14, 12, tzinfo=UTC)
    tickers_observed_at = scan_started_at + timedelta(seconds=12)
    gateway = FakeMarketGateway(
        instruments=(instrument(MarketCategory.SPOT, "BTCUSDT"),),
        tickers=(
            ticker(
                MarketCategory.SPOT,
                "BTCUSDT",
                observed_at=tickers_observed_at,
                turnover="1000000",
            ),
        ),
    )
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'slow-refresh.db'}")
    intelligence = IntelligenceStore(engine)
    await intelligence.create_schema()
    clock_values = iter(
        (
            scan_started_at,
            scan_started_at + timedelta(seconds=6),
            tickers_observed_at,
        )
    )
    service = MarketService(
        store=MarketStore(intelligence.sessions),
        gateway=gateway,
        clock=lambda: next(clock_values),
    )

    scan = await service.run_scan(environment=BrokerEnvironment.MAINNET)

    assert scan.source_count == 1
    assert scan.created_at == tickers_observed_at
    await engine.dispose()


@pytest.mark.asyncio
async def test_scan_persists_parent_before_candidates_with_foreign_keys_enabled(tmp_path):
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    gateway = FakeMarketGateway(
        instruments=(instrument(MarketCategory.SPOT, "BTCUSDT"),),
        tickers=(
            ticker(
                MarketCategory.SPOT,
                "BTCUSDT",
                observed_at=now,
                turnover="1000000",
            ),
        ),
    )
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'foreign-keys.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    intelligence = IntelligenceStore(engine)
    await intelligence.create_schema()
    service = MarketService(
        store=MarketStore(intelligence.sessions),
        gateway=gateway,
        clock=lambda: now,
    )

    scan = await service.run_scan(environment=BrokerEnvironment.MAINNET)

    assert await service.latest_scan(environment=BrokerEnvironment.MAINNET) == scan
    await engine.dispose()


@pytest.mark.asyncio
async def test_scan_rejects_stale_market_data(tmp_path):
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    gateway = FakeMarketGateway(
        instruments=(instrument(MarketCategory.SPOT, "BTCUSDT"),),
        tickers=(
            ticker(
                MarketCategory.SPOT,
                "BTCUSDT",
                observed_at=now - timedelta(minutes=1),
                turnover="1000000",
            ),
        ),
    )
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'stale.db'}")
    intelligence = IntelligenceStore(engine)
    await intelligence.create_schema()
    service = MarketService(
        store=MarketStore(intelligence.sessions),
        gateway=gateway,
        max_data_age=timedelta(seconds=30),
        clock=lambda: now,
    )

    with pytest.raises(StaleMarketDataError):
        await service.run_scan(environment=BrokerEnvironment.MAINNET)

    await engine.dispose()


@pytest.mark.asyncio
async def test_analysis_requests_are_deduplicated_claimed_and_completed(tmp_path):
    now = datetime(2026, 8, 17, 9, tzinfo=UTC)
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'analysis-requests.db'}")
    intelligence = IntelligenceStore(engine)
    await intelligence.create_schema()
    store = MarketStore(intelligence.sessions)
    service = MarketService(
        store=store,
        gateway=FakeMarketGateway(instruments=(), tickers=()),
        clock=lambda: now,
    )

    first = await service.request_analysis(
        user_id="user-1",
        environment=BrokerEnvironment.MAINNET,
    )
    duplicate = await service.request_analysis(
        user_id="user-1",
        environment=BrokerEnvironment.MAINNET,
    )
    claimed = await service.claim_analysis_requests(
        environment=BrokerEnvironment.MAINNET,
        limit=20,
    )
    await service.complete_analysis_requests(
        requests=claimed,
        scan_id="scan-1",
    )
    completed = await service.analysis_request(
        user_id="user-1",
        request_id=first.id,
    )
    next_request = await service.request_analysis(
        user_id="user-1",
        environment=BrokerEnvironment.MAINNET,
    )

    assert duplicate.id == first.id
    assert claimed[0].status is MarketAnalysisRequestStatus.RUNNING
    assert completed is not None
    assert completed.status is MarketAnalysisRequestStatus.COMPLETED
    assert completed.scan_id == "scan-1"
    assert next_request.id != first.id
    await engine.dispose()


@pytest.mark.asyncio
async def test_stale_running_analysis_request_is_reclaimed_after_worker_restart(tmp_path):
    clock_now = [datetime(2026, 8, 17, 9, tzinfo=UTC)]
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'stale-analysis-request.db'}")
    intelligence = IntelligenceStore(engine)
    await intelligence.create_schema()
    service = MarketService(
        store=MarketStore(intelligence.sessions),
        gateway=FakeMarketGateway(instruments=(), tickers=()),
        clock=lambda: clock_now[0],
    )
    requested = await service.request_analysis(
        user_id="user-1",
        environment=BrokerEnvironment.MAINNET,
    )
    first_claim = await service.claim_analysis_requests(
        environment=BrokerEnvironment.MAINNET,
    )

    clock_now[0] += timedelta(minutes=11)
    reclaimed = await service.claim_analysis_requests(
        environment=BrokerEnvironment.MAINNET,
    )

    assert first_claim[0].id == requested.id
    assert reclaimed[0].id == requested.id
    assert reclaimed[0].started_at == clock_now[0]
    await engine.dispose()
