from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from signalos_backend.brokers.domain import BrokerEnvironment
from signalos_backend.market.domain import (
    Instrument,
    MarketAnalysisRequest,
    MarketReview,
    MarketScan,
    TickerSnapshot,
)
from signalos_backend.market.scanner import rank_market
from signalos_backend.market.store import MarketStore


class MarketDataGateway(Protocol):
    async def get_instruments(
        self, *, environment: BrokerEnvironment
    ) -> tuple[Instrument, ...]: ...

    async def get_tickers(
        self, *, environment: BrokerEnvironment
    ) -> tuple[TickerSnapshot, ...]: ...


class MarketDataError(RuntimeError):
    pass


class StaleMarketDataError(MarketDataError):
    pass


class MarketService:
    def __init__(
        self,
        *,
        store: MarketStore,
        gateway: MarketDataGateway,
        max_data_age: timedelta = timedelta(seconds=30),
        instrument_refresh_interval: timedelta = timedelta(hours=6),
        analysis_request_lease: timedelta = timedelta(minutes=10),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.gateway = gateway
        self.max_data_age = max_data_age
        self.instrument_refresh_interval = instrument_refresh_interval
        self.analysis_request_lease = analysis_request_lease
        self.clock = clock or (lambda: datetime.now(UTC))

    async def refresh_universe(self, *, environment: BrokerEnvironment) -> tuple[Instrument, ...]:
        instruments = await self.gateway.get_instruments(environment=environment)
        if not instruments:
            raise MarketDataError("Bybit returned an empty eligible USDT universe")
        await self.store.replace_instruments(
            environment=environment,
            instruments=instruments,
            refreshed_at=self.clock(),
        )
        return instruments

    async def run_scan(self, *, environment: BrokerEnvironment) -> MarketScan:
        scan_started_at = self.clock()
        refreshed_at = await self.store.instrument_refresh_time(environment=environment)
        if (
            refreshed_at is None
            or scan_started_at - _as_utc(refreshed_at) >= self.instrument_refresh_interval
        ):
            instruments = await self.refresh_universe(environment=environment)
        else:
            instruments = await self.store.list_instruments(environment=environment)

        eligible = {(item.category, item.symbol) for item in instruments}
        raw_snapshots = await self.gateway.get_tickers(environment=environment)
        snapshots = tuple(
            item for item in raw_snapshots if (item.category, item.symbol) in eligible
        )
        if not snapshots:
            raise MarketDataError("Bybit returned no tickers for the eligible universe")
        validated_at = self.clock()
        if any(
            item.observed_at > validated_at + timedelta(seconds=5)
            or validated_at - item.observed_at > self.max_data_age
            for item in snapshots
        ):
            raise StaleMarketDataError("Bybit ticker feed is stale or has invalid clock skew")

        await self.store.replace_latest_tickers(
            environment=environment,
            snapshots=snapshots,
        )
        result = rank_market(snapshots)
        scan = MarketScan(
            id=str(uuid4()),
            environment=environment,
            source_count=len(snapshots),
            observed_at=max(item.observed_at for item in snapshots),
            created_at=validated_at,
            result=result,
        )
        await self.store.save_scan(scan)
        return scan

    async def latest_scan(self, *, environment: BrokerEnvironment) -> MarketScan | None:
        return await self.store.latest_scan(environment=environment)

    async def latest_review(self, *, environment: BrokerEnvironment) -> MarketReview | None:
        return await self.store.latest_review(environment=environment)

    async def request_analysis(
        self,
        *,
        user_id: str,
        environment: BrokerEnvironment,
    ) -> MarketAnalysisRequest:
        return await self.store.request_analysis(
            request_id=str(uuid4()),
            user_id=user_id,
            environment=environment,
            requested_at=self.clock(),
        )

    async def analysis_request(
        self,
        *,
        user_id: str,
        request_id: str,
    ) -> MarketAnalysisRequest | None:
        return await self.store.analysis_request(user_id=user_id, request_id=request_id)

    async def claim_analysis_requests(
        self,
        *,
        environment: BrokerEnvironment,
        limit: int = 100,
    ) -> tuple[MarketAnalysisRequest, ...]:
        started_at = self.clock()
        return await self.store.claim_analysis_requests(
            environment=environment,
            started_at=started_at,
            stale_before=started_at - self.analysis_request_lease,
            limit=limit,
        )

    async def complete_analysis_requests(
        self,
        *,
        requests: tuple[MarketAnalysisRequest, ...],
        scan_id: str,
    ) -> None:
        await self.store.complete_analysis_requests(
            requests=requests,
            scan_id=scan_id,
            completed_at=self.clock(),
        )

    async def fail_analysis_requests(
        self,
        *,
        requests: tuple[MarketAnalysisRequest, ...],
        error_code: str,
    ) -> None:
        await self.store.fail_analysis_requests(
            requests=requests,
            error_code=error_code,
            completed_at=self.clock(),
        )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
