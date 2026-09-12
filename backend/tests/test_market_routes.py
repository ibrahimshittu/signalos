from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from signalos_backend.brokers.domain import BrokerEnvironment
from signalos_backend.config import Settings
from signalos_backend.main import create_app
from signalos_backend.market.domain import (
    Instrument,
    MarketAnalysisRequest,
    MarketAnalysisRequestStatus,
    MarketCategory,
    MarketReview,
    MarketReviewCandidate,
    MarketReviewStatus,
    TickerSnapshot,
)

USER_HEADERS = {"X-SignalOS-User-Id": "market-user"}


class FakeMarketGateway:
    async def get_instruments(self, *, environment: BrokerEnvironment) -> tuple[Instrument, ...]:
        assert environment is BrokerEnvironment.MAINNET
        return (
            Instrument(
                category=MarketCategory.SPOT,
                symbol="BTCUSDT",
                base_coin="BTC",
                quote_coin="USDT",
                status="Trading",
                tick_size=Decimal("0.01"),
                quantity_step=Decimal("0.0001"),
                minimum_order_quantity=Decimal("0.0001"),
                minimum_notional=Decimal("5"),
                funding_interval_minutes=None,
            ),
        )

    async def get_tickers(self, *, environment: BrokerEnvironment) -> tuple[TickerSnapshot, ...]:
        assert environment is BrokerEnvironment.MAINNET
        return (
            TickerSnapshot(
                category=MarketCategory.SPOT,
                symbol="BTCUSDT",
                last_price=Decimal("65000"),
                bid_price=Decimal("64999"),
                ask_price=Decimal("65001"),
                turnover_24h=Decimal("500000000"),
                volume_24h=Decimal("10000"),
                price_change_24h=Decimal("0.025"),
                observed_at=datetime.now(UTC),
            ),
        )


def test_latest_scan_is_nullable_and_a_user_can_run_a_real_scan(tmp_path):
    app = create_app(
        Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'market-routes.db'}",
            api_key="operator",
            logfire_send=False,
        )
    )
    app.state.studio.markets.gateway = FakeMarketGateway()

    with TestClient(app) as client:
        empty = client.get(
            "/v1/market-scans/latest?environment=mainnet",
            headers=USER_HEADERS,
        )
        assert empty.status_code == 200
        assert empty.json() is None

        created = client.post(
            "/v1/market-scans?environment=mainnet",
            headers=USER_HEADERS,
        )
        assert created.status_code == 201
        assert created.json()["source_count"] == 1
        assert created.json()["result"]["hot_universe"][0]["symbol"] == "BTCUSDT"

        latest = client.get(
            "/v1/market-scans/latest?environment=mainnet",
            headers=USER_HEADERS,
        )
        assert latest.status_code == 200
        assert latest.json()["id"] == created.json()["id"]


def test_latest_market_review_is_a_bounded_explanation_feed(tmp_path):
    app = create_app(
        Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'market-review-routes.db'}",
            api_key="operator",
            logfire_send=False,
        )
    )
    reviewed_at = datetime(2026, 8, 15, 10, tzinfo=UTC)
    app.state.studio.markets.latest_review = AsyncMock(
        return_value=MarketReview(
            scan_id="scan-1",
            environment=BrokerEnvironment.MAINNET,
            analyzed_at=reviewed_at,
            approved_strategies=0,
            candidates_considered=1,
            strategy_matches=0,
            signals_found=0,
            analysis_completed=0,
            no_trade_decisions=0,
            proposals_created=0,
            duplicates_skipped=0,
            gate_rejections=0,
            model_available=True,
            candidates=(
                MarketReviewCandidate(
                    category=MarketCategory.LINEAR,
                    symbol="BTCUSDT",
                    rank=1,
                    status=MarketReviewStatus.NO_APPROVED_STRATEGY,
                    reason="No live strategy is available for trade analysis.",
                    strategy_id=None,
                ),
            ),
        )
    )

    with TestClient(app) as client:
        response = client.get(
            "/v1/market-reviews/latest?environment=mainnet",
            headers=USER_HEADERS,
        )

    assert response.status_code == 200
    assert response.json()["candidates"][0] == {
        "category": "linear",
        "symbol": "BTCUSDT",
        "rank": 1,
        "status": "no_approved_strategy",
        "reason": "No live strategy is available for trade analysis.",
        "strategy_id": None,
        "portfolio_review": None,
    }


def test_user_can_request_and_track_a_fresh_market_analysis(tmp_path):
    app = create_app(
        Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'analysis-request-routes.db'}",
            api_key="operator",
            logfire_send=False,
        )
    )
    requested_at = datetime(2026, 8, 17, 9, tzinfo=UTC)
    request = MarketAnalysisRequest(
        id="4b7c4952-6be2-4a25-a113-787323bdd163",
        environment=BrokerEnvironment.MAINNET,
        status=MarketAnalysisRequestStatus.QUEUED,
        requested_at=requested_at,
    )
    app.state.studio.markets.request_analysis = AsyncMock(return_value=request)
    app.state.studio.markets.analysis_request = AsyncMock(return_value=request)

    with TestClient(app) as client:
        created = client.post(
            "/v1/market-analysis-requests?environment=mainnet",
            headers=USER_HEADERS,
        )
        tracked = client.get(
            f"/v1/market-analysis-requests/{request.id}",
            headers=USER_HEADERS,
        )

    assert created.status_code == 202
    assert created.json() == {
        "id": request.id,
        "environment": "mainnet",
        "status": "queued",
        "requested_at": "2026-08-17T09:00:00Z",
        "started_at": None,
        "completed_at": None,
        "scan_id": None,
        "error_code": None,
    }
    assert tracked.status_code == 200
    app.state.studio.markets.request_analysis.assert_awaited_once_with(
        user_id="market-user",
        environment=BrokerEnvironment.MAINNET,
    )
    app.state.studio.markets.analysis_request.assert_awaited_once_with(
        user_id="market-user",
        request_id=request.id,
    )


def test_analysis_request_is_private_to_the_authenticated_user(tmp_path):
    app = create_app(
        Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'private-analysis-request.db'}",
            api_key="operator",
            logfire_send=False,
        )
    )
    app.state.studio.markets.analysis_request = AsyncMock(return_value=None)

    with TestClient(app) as client:
        response = client.get(
            "/v1/market-analysis-requests/4b7c4952-6be2-4a25-a113-787323bdd163",
            headers=USER_HEADERS,
        )

    assert response.status_code == 404
