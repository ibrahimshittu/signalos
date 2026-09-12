from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from signalos_backend.brokers.domain import (
    AccountBalance,
    AccountSnapshot,
    BrokerEnvironment,
    BybitKeyInfo,
    CreateBrokerConnection,
)
from signalos_backend.brokers.service import BrokerService
from signalos_backend.brokers.store import BrokerStore
from signalos_backend.config import Settings
from signalos_backend.db import IntelligenceStore, build_engine
from signalos_backend.domain import StrategyStatus
from signalos_backend.execution.domain import BrokerPositionSnapshot
from signalos_backend.execution.store import ExecutionStore
from signalos_backend.intelligence.laboratory import ExperimentResult
from signalos_backend.intelligence.registries import StrategyRegistry
from signalos_backend.investment.domain import (
    DecisionAction,
    InvestmentDecision,
    PortfolioAdvice,
)
from signalos_backend.investment.pipeline import InvestmentPipeline
from signalos_backend.market.domain import (
    Candle,
    Instrument,
    MarketCandidate,
    MarketCategory,
    MarketReviewStatus,
    MarketScan,
    MarketScanResult,
    TickerSnapshot,
)
from signalos_backend.market.service import MarketService
from signalos_backend.market.store import MarketStore
from signalos_backend.proposals.service import ProposalService
from signalos_backend.proposals.store import ProposalStore
from signalos_backend.security.credentials import CredentialCipher
from signalos_backend.seeds import build_strategy_registry
from signalos_backend.users.domain import InvestmentProfileInput
from signalos_backend.users.memory import UserMemoryStore
from signalos_backend.users.store import UserStore


class FakeLiveBybit:
    def __init__(self, now: datetime) -> None:
        self.now = now
        self.account_syncs = 0

    async def get_key_info(self, **kwargs):
        del kwargs
        return BybitKeyInfo(
            user_id="123",
            parent_uid="0",
            is_master=True,
            read_only=False,
            ips=("203.0.113.10",),
            permissions={"ContractTrade": ("Order", "Position"), "Wallet": ()},
        )

    async def get_account_snapshot(self, **kwargs):
        del kwargs
        self.account_syncs += 1
        return AccountSnapshot(
            account_type="UNIFIED",
            total_equity=Decimal("10000"),
            available_balance=Decimal("7000"),
            balances=(
                AccountBalance(
                    coin="USDT",
                    wallet_balance=Decimal("10000"),
                    equity=Decimal("10000"),
                    available_to_withdraw=Decimal("7000"),
                ),
            ),
            captured_at=self.now,
        )

    async def get_instruments(self, **kwargs):
        del kwargs
        return (
            Instrument(
                category=MarketCategory.LINEAR,
                symbol="BTCUSDT",
                base_coin="BTC",
                quote_coin="USDT",
                status="Trading",
                tick_size=Decimal("0.1"),
                quantity_step=Decimal("0.001"),
                minimum_order_quantity=Decimal("0.001"),
                minimum_notional=Decimal("5"),
                funding_interval_minutes=480,
            ),
        )

    async def get_tickers(self, **kwargs):
        del kwargs
        return (
            TickerSnapshot(
                category=MarketCategory.LINEAR,
                symbol="BTCUSDT",
                last_price=Decimal("111.8"),
                bid_price=Decimal("111.7"),
                ask_price=Decimal("111.9"),
                turnover_24h=Decimal("1000000000"),
                volume_24h=Decimal("100000"),
                price_change_24h=Decimal("0.04"),
                open_interest=Decimal("500000"),
                funding_rate=Decimal("0.0001"),
                observed_at=self.now,
            ),
        )

    async def get_closed_klines(self, **kwargs):
        del kwargs
        start = self.now - timedelta(minutes=15 * 60)
        return tuple(
            Candle(
                category=MarketCategory.LINEAR,
                symbol="BTCUSDT",
                interval_minutes=15,
                start_at=start + timedelta(minutes=15 * index),
                end_at=start + timedelta(minutes=15 * (index + 1)),
                open_price=(price := Decimal("100") + Decimal("0.2") * index) - Decimal("0.1"),
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal(100 + index),
                turnover=price * Decimal(100 + index),
            )
            for index in range(60)
        )

    async def get_max_leverage(self, **kwargs):
        del kwargs
        return Decimal("100")


class FakeDirector:
    def __init__(self) -> None:
        self.advisor_calls = 0
        self.positions_seen = 0

    async def analyze(self, deps):
        return InvestmentDecision(
            candidate_symbol=deps.candidate.symbol,
            action=DecisionAction.PROPOSE,
            thesis=(
                "The completed-candle trend, activity ranking, and liquid spread support a "
                "bounded continuation setup."
            ),
            opposing_case=(
                "The move can fail if the trend loses its fast average or liquidity deteriorates."
            ),
            confidence=Decimal("0.80"),
            requested_leverage=Decimal("15"),
            limitations=("The market can gap through the reviewed stop price.",),
        )

    async def advise(self, deps):
        self.advisor_calls += 1
        self.positions_seen = len(deps.positions)
        return PortfolioAdvice(
            suitable=True,
            summary="The opportunity remains bounded after considering the live position book.",
            why_it_fits=(
                "Current margin, directional exposure, and the explicit growth mandate support "
                "a reduced, stop-defined position."
            ),
            why_reject=(
                "Reject if adding another long crypto exposure is inconsistent with the desired "
                "portfolio concentration."
            ),
            risk_concerns=("Existing long crypto exposure increases correlated downside.",),
            leverage_ceiling=Decimal("10"),
            confidence_multiplier=Decimal("0.80"),
        )


def advanced_profile() -> InvestmentProfileInput:
    return InvestmentProfileInput(
        goals=("capital_growth",),
        intended_capital=Decimal("10000"),
        time_horizon="swing",
        liquidity_need="low",
        investing_experience="advanced",
        trading_experience="advanced",
        products_traded=("stocks_etfs", "crypto_spot", "futures"),
        decision_frequency="weekly",
        drawdown_response="hold",
        holding_periods=("intraday", "multi_day"),
        explanation_detail="detailed",
        notification_frequency="opportunities_only",
        disclosures_accepted=True,
    )


def approved_strategy() -> StrategyRegistry:
    original = build_strategy_registry().get("managed-trend-filter")
    candidate = original.model_copy(
        update={
            "evidence_references": (f"evaluation:{'a' * 64}",),
            "risk_constraints": original.risk_constraints.model_copy(
                update={"leverage_max": Decimal("20")}
            ),
        }
    )
    registry = StrategyRegistry()
    registry.register_candidate(candidate)
    for status in (
        StrategyStatus.RESEARCH,
        StrategyStatus.VALIDATED,
        StrategyStatus.SHADOW,
        StrategyStatus.PROMOTION_PENDING,
        StrategyStatus.APPROVED,
    ):
        registry.transition(
            candidate.id,
            candidate.version,
            status,
            operator_approved=status is StrategyStatus.APPROVED,
        )
    return registry


def review_scan(now: datetime, symbol: str = "PORTALUSDT") -> MarketScan:
    candidate = MarketCandidate(
        category=MarketCategory.LINEAR,
        symbol=symbol,
        activity_score=Decimal("0.9"),
        turnover_24h=Decimal("1000000"),
        price_change_24h=Decimal("0.1"),
        spread_bps=Decimal("2"),
        observed_at=now,
    )
    return MarketScan(
        id="scan-review",
        environment=BrokerEnvironment.MAINNET,
        source_count=1,
        observed_at=now,
        created_at=now,
        result=MarketScanResult(hot_universe=(candidate,), agent_shortlist=(candidate,)),
    )


def review_instrument(symbol: str = "PORTALUSDT") -> Instrument:
    return Instrument(
        category=MarketCategory.LINEAR,
        symbol=symbol,
        base_coin=symbol.removesuffix("USDT"),
        quote_coin="USDT",
        status="Trading",
        tick_size=Decimal("0.0001"),
        quantity_step=Decimal("1"),
        minimum_order_quantity=Decimal("1"),
        minimum_notional=Decimal("5"),
        funding_interval_minutes=480,
    )


def review_ticker(now: datetime, symbol: str = "PORTALUSDT") -> TickerSnapshot:
    return TickerSnapshot(
        category=MarketCategory.LINEAR,
        symbol=symbol,
        last_price=Decimal("0.25"),
        bid_price=Decimal("0.2499"),
        ask_price=Decimal("0.2501"),
        turnover_24h=Decimal("1000000"),
        volume_24h=Decimal("4000000"),
        price_change_24h=Decimal("0.1"),
        observed_at=now,
    )


def review_pipeline(*, strategies: StrategyRegistry, now: datetime):
    market_store = MagicMock()
    market_store.get_instrument = AsyncMock(return_value=review_instrument())
    market_store.get_ticker = AsyncMock(return_value=review_ticker(now))
    market_store.save_review = AsyncMock()
    pipeline = InvestmentPipeline(
        market_store=market_store,
        market_gateway=MagicMock(),
        intelligence_store=MagicMock(),
        strategies=strategies,
        users=MagicMock(),
        brokers=MagicMock(),
        account_sync=MagicMock(),
        position_store=MagicMock(),
        memories=MagicMock(),
        proposals=MagicMock(),
        proposal_store=MagicMock(),
        agents=FakeDirector(),
        clock=lambda: now,
    )
    return pipeline, market_store


@pytest.mark.asyncio
async def test_review_distinguishes_an_unavailable_strategy_catalog() -> None:
    now = datetime(2026, 8, 17, 9, tzinfo=UTC)
    pipeline, market_store = review_pipeline(
        strategies=build_strategy_registry(),
        now=now,
    )

    await pipeline.analyze_scan(review_scan(now))

    review = market_store.save_review.await_args.args[0]
    assert review.approved_strategies == 0
    assert review.candidates[0].status is MarketReviewStatus.NO_APPROVED_STRATEGY
    assert review.candidates[0].reason == "No live strategy is available for trade analysis."


@pytest.mark.asyncio
async def test_review_distinguishes_a_market_outside_approved_strategy_coverage() -> None:
    now = datetime(2026, 8, 17, 9, tzinfo=UTC)
    pipeline, market_store = review_pipeline(strategies=approved_strategy(), now=now)

    await pipeline.analyze_scan(review_scan(now))

    review = market_store.save_review.await_args.args[0]
    assert review.approved_strategies == 1
    assert review.candidates[0].status is MarketReviewStatus.NO_STRATEGY_MATCH
    assert review.candidates[0].reason == "No live strategy covers this market."


@pytest.mark.asyncio
async def test_live_scan_creates_one_personalized_proposal_without_mock_data(tmp_path) -> None:
    now = datetime(2026, 8, 14, 15, tzinfo=UTC)
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'pipeline.db'}")
    database = IntelligenceStore(engine)
    await database.create_schema()
    users = UserStore(database.sessions)
    brokers = BrokerStore(database.sessions)
    market_store = MarketStore(database.sessions)
    proposals = ProposalStore(database.sessions)
    memories = UserMemoryStore(database.sessions)
    execution_store = ExecutionStore(database.sessions)
    await users.save_profile("user-a", advanced_profile())

    cipher = CredentialCipher(
        (base64.urlsafe_b64encode(b"pipeline-test-key-material-00000").decode(),)
    )
    live_bybit = FakeLiveBybit(now)
    broker_service = BrokerService(
        Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:"),
        brokers,
        cipher,
        live_bybit,
    )
    connection = await broker_service.create(
        user_id="user-a",
        payload=CreateBrokerConnection(
            provider_id="bybit",
            environment=BrokerEnvironment.MAINNET,
            api_key="write-key",
            api_secret="write-secret",
        ),
    )
    await broker_service.verify(user_id="user-a", connection_id=connection.id)
    await broker_service.sync(user_id="user-a", connection_id=connection.id)
    await execution_store.replace_open_positions(
        user_id="user-a",
        connection_id=connection.id,
        environment=BrokerEnvironment.MAINNET,
        snapshots=(
            BrokerPositionSnapshot(
                category=MarketCategory.LINEAR,
                symbol="ETHUSDT",
                position_index=0,
                side="buy",
                size=Decimal("1"),
                average_price=Decimal("3000"),
                position_value=Decimal("3000"),
                leverage=Decimal("3"),
                mark_price=Decimal("3000"),
                liquidation_price=Decimal("1500"),
                take_profit=Decimal("3300"),
                stop_loss=Decimal("2800"),
                unrealised_pnl=Decimal("0"),
                cumulative_realised_pnl=Decimal("0"),
                sequence=1,
                updated_at=now,
            ),
        ),
        reconciled_at=now,
    )

    await database.save_evaluation(
        ExperimentResult(
            strategy_id="managed-trend-filter",
            strategy_version="1.0.0",
            decisions=150,
            regimes_observed=3,
            gross_return=Decimal("0.20"),
            net_return=Decimal("0.15"),
            baseline_return=Decimal("0.10"),
            annualized_sharpe=Decimal("1.2"),
            max_drawdown=Decimal("0.08"),
            turnover=Decimal("3"),
            cost_paid=Decimal("0.01"),
            sensitivity_stable=True,
            reproducibility_hash="a" * 64,
            passed_gates=True,
            failures=(),
        )
    )
    scan = await MarketService(
        store=market_store,
        gateway=live_bybit,
        clock=lambda: now,
    ).run_scan(environment=BrokerEnvironment.MAINNET)
    director = FakeDirector()
    pipeline = InvestmentPipeline(
        market_store=market_store,
        market_gateway=live_bybit,
        intelligence_store=database,
        strategies=approved_strategy(),
        users=users,
        brokers=brokers,
        account_sync=broker_service,
        position_store=execution_store,
        memories=memories,
        proposals=ProposalService(
            users=users,
            brokers=brokers,
            proposals=proposals,
            memories=memories,
            clock=lambda: now,
        ),
        proposal_store=proposals,
        agents=director,
        clock=lambda: now,
    )

    first = await pipeline.analyze_scan(scan)
    second = await pipeline.analyze_scan(scan)
    stored = await proposals.list(user_id="user-a")
    review = await market_store.latest_review(environment=BrokerEnvironment.MAINNET)

    assert first.analysis_completed == 1
    assert first.proposals_created == 1
    assert second.proposals_created == 0
    assert second.duplicates_skipped == 1
    assert len(stored) == 1
    assert stored[0].leverage < Decimal("15")
    assert stored[0].estimated_max_loss <= Decimal("100")
    assert stored[0].gate_report.passed is True
    assert "Current margin" in stored[0].why_it_fits
    assert director.advisor_calls == 1
    assert director.positions_seen == 1
    assert live_bybit.account_syncs == 2
    assert review is not None
    assert review.scan_id == scan.id
    assert review.candidates[0].status is MarketReviewStatus.PASSED_MARKET_CHECKS
    assert review.candidates[0].strategy_id == "managed-trend-filter"
    private = await market_store.review_for_account(
        review, user_id="user-a", connection_id=stored[0].connection_id
    )
    assert private.candidates[0].portfolio_review.code == "already_proposed"
    other = await market_store.review_for_account(
        review, user_id="user-b", connection_id=stored[0].connection_id
    )
    assert other.candidates[0].portfolio_review is None
    assert review.candidates[0].portfolio_review is None
    await engine.dispose()
