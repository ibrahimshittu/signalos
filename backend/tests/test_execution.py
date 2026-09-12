from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

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
from signalos_backend.execution.domain import (
    BrokerOrderAcknowledgement,
    BrokerOrderSnapshot,
    BrokerOrderState,
    BrokerPositionSnapshot,
    ConfirmExecutionActionInput,
    ExecutionActionState,
    ExecutionConflictError,
    SubmitOrderInput,
    UpdateProtectionInput,
)
from signalos_backend.execution.portfolio import position_portfolio_fingerprint
from signalos_backend.execution.service import ExecutionService
from signalos_backend.execution.store import ExecutionStore
from signalos_backend.intelligence.laboratory import ExperimentResult
from signalos_backend.investment.gates import MandatoryGateReport
from signalos_backend.market.domain import MarketCategory, TickerSnapshot
from signalos_backend.proposals.domain import (
    CreateTradeProposal,
    OrderSide,
    OrderType,
    ProposalStatus,
)
from signalos_backend.proposals.service import ProposalService
from signalos_backend.proposals.store import ProposalStore
from signalos_backend.security.credentials import CredentialCipher
from signalos_backend.seeds import build_strategy_registry
from signalos_backend.users.domain import InvestmentProfileInput
from signalos_backend.users.store import UserStore


class FakeBybit:
    def __init__(self) -> None:
        self.orders = 0
        self.leverage_updates = 0
        self.cancellations = 0
        self.position_closes = 0
        self.protection_updates = 0
        self.position = BrokerPositionSnapshot(
            category="linear",
            symbol="BTCUSDT",
            position_index=0,
            side=OrderSide.BUY,
            size=Decimal("0.01"),
            average_price=Decimal("68000"),
            position_value=Decimal("680"),
            leverage=Decimal("2"),
            mark_price=Decimal("68100"),
            liquidation_price=Decimal("35000"),
            take_profit=Decimal("70000"),
            stop_loss=Decimal("67000"),
            unrealised_pnl=Decimal("1"),
            cumulative_realised_pnl=Decimal("-0.34"),
            sequence=42,
            updated_at=datetime(2026, 8, 15, 12, tzinfo=UTC),
        )

    async def get_key_info(self, *, api_key, api_secret, environment):
        del api_key, api_secret, environment
        return BybitKeyInfo(
            user_id="123",
            parent_uid="0",
            is_master=True,
            read_only=False,
            ips=("203.0.113.10",),
            permissions={"ContractTrade": ("Order", "Position"), "Wallet": ()},
        )

    async def get_account_snapshot(self, *, api_key, api_secret, environment):
        del api_key, api_secret, environment
        return AccountSnapshot(
            account_type="UNIFIED",
            total_equity=Decimal("10000"),
            available_balance=Decimal("7000"),
            balances=(
                AccountBalance(
                    coin="USDT",
                    wallet_balance=Decimal("7000"),
                    equity=Decimal("7000"),
                    available_to_withdraw=Decimal("7000"),
                ),
            ),
        )

    async def set_leverage(self, **kwargs):
        del kwargs
        self.leverage_updates += 1

    async def place_order(self, **kwargs):
        self.orders += 1
        return BrokerOrderAcknowledgement(
            order_id="bybit-order-1",
            order_link_id=kwargs["order_link_id"],
        )

    async def get_order_snapshot(self, **kwargs):
        return BrokerOrderSnapshot(
            order_id="bybit-order-1",
            order_link_id=kwargs["order_link_id"],
            category="linear",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            status="New",
            quantity=Decimal("0.01"),
            cumulative_executed_quantity=Decimal("0"),
            leaves_quantity=Decimal("0.01"),
            average_price=None,
            updated_at=datetime(2026, 8, 15, 12, tzinfo=UTC),
        )

    async def cancel_order(self, **kwargs):
        self.cancellations += 1
        return BrokerOrderAcknowledgement(
            order_id=kwargs["order_id"],
            order_link_id=kwargs["order_link_id"],
        )

    async def get_positions(self, **kwargs):
        del kwargs
        return (self.position,)

    async def close_position(self, **kwargs):
        self.position_closes += 1
        return BrokerOrderAcknowledgement(
            order_id="close-order-1",
            order_link_id=kwargs["order_link_id"],
        )

    async def set_trading_stop(self, **kwargs):
        self.protection_updates += 1

    async def get_max_leverage(self, **kwargs):
        del kwargs
        return Decimal("100")

    async def get_ticker_snapshot(self, **kwargs):
        return TickerSnapshot(
            category=MarketCategory(kwargs["category"]),
            symbol=kwargs["symbol"],
            last_price=Decimal("68010"),
            bid_price=Decimal("68009"),
            ask_price=Decimal("68011"),
            turnover_24h=Decimal("1000000000"),
            volume_24h=Decimal("10000"),
            price_change_24h=Decimal("0.01"),
            open_interest=Decimal("100000"),
            funding_rate=Decimal("0.0001"),
            observed_at=datetime(2026, 8, 15, 12, tzinfo=UTC),
        )


def profile() -> InvestmentProfileInput:
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


@pytest.mark.asyncio
async def test_user_review_submits_exact_proposal_once(tmp_path):
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'execution.db'}")
    database = IntelligenceStore(engine)
    users = UserStore(database.sessions)
    brokers = BrokerStore(database.sessions)
    proposals = ProposalStore(database.sessions)
    executions = ExecutionStore(database.sessions)
    await database.create_schema()
    await users.save_profile("user-a", profile())

    cipher = CredentialCipher(
        (base64.urlsafe_b64encode(b"execution-test-key-material-0000").decode(),)
    )
    gateway = FakeBybit()
    broker_service = BrokerService(
        Settings(environment="test", database_url="sqlite+aiosqlite:///:memory:"),
        brokers,
        cipher,
        gateway,
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
    await executions.replace_open_positions(
        user_id="user-a",
        connection_id=connection.id,
        environment=BrokerEnvironment.MAINNET,
        snapshots=(gateway.position,),
        reconciled_at=now,
    )
    bound_portfolio = await executions.get_position_portfolio(
        user_id="user-a", connection_id=connection.id
    )
    assert bound_portfolio is not None

    proposal = await ProposalService(
        users=users,
        brokers=brokers,
        proposals=proposals,
        clock=lambda: now,
    ).create(
        user_id="user-a",
        payload=CreateTradeProposal(
            connection_id=connection.id,
            strategy_id="session-opening-breakout",
            strategy_version="1.0.0",
            strategy_family="session_opening",
            category="linear",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            limit_price=Decimal("68000"),
            stop_loss=Decimal("67000"),
            take_profit=Decimal("70000"),
            leverage=Decimal("2"),
            estimated_fees=Decimal("1"),
            estimated_funding=Decimal("0.20"),
            estimated_slippage=Decimal("2"),
            estimated_max_loss=Decimal("10"),
            required_margin=Decimal("340"),
            portfolio_fingerprint=position_portfolio_fingerprint(bound_portfolio.positions),
            position_reconciled_at=bound_portfolio.reconciled_at,
            market_price=Decimal("68010"),
            market_observed_at=now - timedelta(seconds=10),
            expires_at=now + timedelta(minutes=3),
            thesis="The opening range reclaimed with improving depth and relative strength.",
            opposing_case="A failed reclaim would invalidate the setup before continuation.",
            why_it_fits="The bounded loss fits the user's adaptive mandate and current portfolio.",
            why_reject="Reject if the defined loss or short holding period feels uncomfortable.",
            gate_report=MandatoryGateReport(passed=True, failures=()),
        ),
    )
    strategy = (
        build_strategy_registry()
        .list_latest()[0]
        .model_copy(
            update={
                "id": proposal.strategy_id,
                "version": proposal.strategy_version,
                "status": StrategyStatus.BENCHED,
            }
        )
    )
    await database.save_strategy(strategy)
    service = ExecutionService(
        proposals=proposals,
        users=users,
        intelligence=database,
        brokers=brokers,
        executions=executions,
        cipher=cipher,
        gateway=gateway,
        clock=lambda: now,
    )

    review = await service.review(user_id="user-a", proposal_id=proposal.id)
    request = SubmitOrderInput(
        review_id=review.id,
        proposal_hash=proposal.proposal_hash,
        idempotency_key="order-submit-1",
    )
    await users.save_profile(
        "user-a",
        InvestmentProfileInput.model_validate(
            {
                **profile().model_dump(),
                "liquidity_need": "high",
            }
        ),
    )
    with pytest.raises(ExecutionConflictError, match="current mandate"):
        await service.submit(user_id="user-a", proposal_id=proposal.id, payload=request)
    assert gateway.orders == 0
    await users.save_profile("user-a", profile())
    with pytest.raises(ExecutionConflictError, match="strategy is no longer approved"):
        await service.submit(user_id="user-a", proposal_id=proposal.id, payload=request)
    assert gateway.orders == 0
    await database.save_strategy(
        strategy.model_copy(
            update={
                "status": StrategyStatus.APPROVED,
                "evidence_references": (f"evaluation:{'a' * 64}",),
            }
        )
    )
    with pytest.raises(ExecutionConflictError, match="strategy evidence is unavailable"):
        await service.submit(user_id="user-a", proposal_id=proposal.id, payload=request)
    assert gateway.orders == 0
    await database.save_evaluation(
        ExperimentResult(
            strategy_id=strategy.id,
            strategy_version=strategy.version,
            decisions=150,
            regimes_observed=3,
            gross_return=Decimal("0.2"),
            net_return=Decimal("0.15"),
            baseline_return=Decimal("0.1"),
            annualized_sharpe=Decimal("1.2"),
            max_drawdown=Decimal("0.04"),
            turnover=Decimal("3"),
            cost_paid=Decimal("0.01"),
            sensitivity_stable=True,
            reproducibility_hash="a" * 64,
            passed_gates=True,
            failures=(),
        )
    )
    original_position = gateway.position
    gateway.position = gateway.position.model_copy(
        update={"size": Decimal("0.02"), "position_value": Decimal("1360"), "sequence": 43}
    )
    with pytest.raises(ExecutionConflictError, match="portfolio changed"):
        await service.submit(
            user_id="user-a",
            proposal_id=proposal.id,
            payload=request.model_copy(update={"idempotency_key": "order-stale-1"}),
        )
    gateway.position = original_position
    first = await service.submit(user_id="user-a", proposal_id=proposal.id, payload=request)
    repeated = await service.submit(user_id="user-a", proposal_id=proposal.id, payload=request)

    assert first.state is BrokerOrderState.ACKNOWLEDGED
    assert first.broker_order_id == "bybit-order-1"
    assert repeated == first
    assert await service.list_orders(user_id="user-a", proposal_id=proposal.id) == (first,)
    assert await service.list_orders(user_id="user-b", proposal_id=proposal.id) == ()
    assert gateway.leverage_updates == 1
    assert gateway.orders == 1
    assert await proposals.has_active(
        user_id="user-a",
        connection_id=connection.id,
        strategy_id=proposal.strategy_id,
        strategy_version=proposal.strategy_version,
        symbol=proposal.symbol,
        now=proposal.expires_at + timedelta(minutes=10),
    )

    cancel_review = await service.review_cancel_order(user_id="user-a", order_id=first.id)
    cancel_request = ConfirmExecutionActionInput(
        review_id=cancel_review.id,
        action_hash=cancel_review.action_hash,
        idempotency_key="cancel-order-1",
    )
    cancel_action = await service.cancel_order(
        user_id="user-a",
        order_id=first.id,
        payload=cancel_request,
    )
    repeated_cancel = await service.cancel_order(
        user_id="user-a",
        order_id=first.id,
        payload=cancel_request,
    )
    assert cancel_action.state is ExecutionActionState.ACKNOWLEDGED
    assert repeated_cancel == cancel_action
    assert gateway.cancellations == 1
    await executions.mark_action(
        action_id=cancel_action.id,
        state=ExecutionActionState.RECONCILIATION_REQUIRED,
        error_code="simulated_transport_unknown",
        now=now,
    )
    await executions.reconcile_order(
        order_id=first.id,
        snapshot=(
            await gateway.get_order_snapshot(order_link_id=first.broker_order_link_id)
        ).model_copy(
            update={
                "status": "Cancelled",
                "leaves_quantity": Decimal("0"),
            }
        ),
        state=BrokerOrderState.CANCELLED,
        reconciled_at=now,
    )
    assert (
        await executions.get_action(user_id="user-a", action_id=cancel_action.id)
    ).state is ExecutionActionState.COMPLETED
    assert (await proposals.get(user_id="user-a", proposal_id=proposal.id)).status is (
        ProposalStatus.ARCHIVED
    )
    assert not await proposals.has_active(
        user_id="user-a",
        connection_id=connection.id,
        strategy_id=proposal.strategy_id,
        strategy_version=proposal.strategy_version,
        symbol=proposal.symbol,
        now=now,
    )
    completed_repeat = await service.cancel_order(
        user_id="user-a",
        order_id=first.id,
        payload=cancel_request,
    )
    assert completed_repeat.state is ExecutionActionState.COMPLETED
    assert gateway.cancellations == 1

    position = (await executions.list_positions(user_id="user-a"))[0]
    assert await service.list_positions(user_id="user-a", connection_id=connection.id) == (
        position,
    )
    assert await service.list_positions(user_id="user-a", connection_id=uuid4()) == ()
    assert await service.list_positions(user_id="user-b", connection_id=connection.id) == ()
    protection_review = await service.review_position_protection(
        user_id="user-a",
        position_id=position.id,
        payload=UpdateProtectionInput(
            stop_loss=Decimal("67500"),
            take_profit=Decimal("70500"),
        ),
    )
    protection_action = await service.update_position_protection(
        user_id="user-a",
        position_id=position.id,
        payload=ConfirmExecutionActionInput(
            review_id=protection_review.id,
            action_hash=protection_review.action_hash,
            idempotency_key="protect-position-1",
        ),
    )
    assert protection_action.state is ExecutionActionState.ACKNOWLEDGED
    assert gateway.protection_updates == 1
    gateway.position = gateway.position.model_copy(
        update={
            "stop_loss": Decimal("67500"),
            "take_profit": Decimal("70500"),
            "sequence": 43,
        }
    )
    await executions.replace_open_positions(
        user_id="user-a",
        connection_id=connection.id,
        environment=BrokerEnvironment.MAINNET,
        snapshots=(gateway.position,),
        reconciled_at=now,
    )
    assert (
        await executions.get_action(user_id="user-a", action_id=protection_action.id)
    ).state is ExecutionActionState.COMPLETED

    close_review = await service.review_close_position(
        user_id="user-a",
        position_id=position.id,
    )
    close_action = await service.close_position(
        user_id="user-a",
        position_id=position.id,
        payload=ConfirmExecutionActionInput(
            review_id=close_review.id,
            action_hash=close_review.action_hash,
            idempotency_key="close-position-1",
        ),
    )
    assert close_action.state is ExecutionActionState.ACKNOWLEDGED
    assert gateway.position_closes == 1
    next_review = await service.review_close_position(user_id="user-a", position_id=position.id)
    with pytest.raises(ExecutionConflictError, match="awaiting broker confirmation"):
        await service.close_position(
            user_id="user-a",
            position_id=position.id,
            payload=ConfirmExecutionActionInput(
                review_id=next_review.id,
                action_hash=next_review.action_hash,
                idempotency_key="duplicate-close-request",
            ),
        )
    assert gateway.position_closes == 1
    await executions.replace_open_positions(
        user_id="user-a",
        connection_id=connection.id,
        environment=BrokerEnvironment.MAINNET,
        snapshots=(),
        reconciled_at=now,
    )
    assert (
        await executions.get_action(user_id="user-a", action_id=close_action.id)
    ).state is ExecutionActionState.COMPLETED
    await engine.dispose()


@pytest.mark.asyncio
async def test_market_order_cannot_open_review_without_bounded_slippage():
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)

    class MarketProposalStore:
        async def get(self, **kwargs):
            del kwargs
            return SimpleNamespace(
                status=ProposalStatus.AVAILABLE,
                expires_at=now + timedelta(minutes=3),
                order_type=OrderType.MARKET,
                limit_price=None,
            )

    service = ExecutionService(
        proposals=MarketProposalStore(),
        users=SimpleNamespace(),
        intelligence=SimpleNamespace(),
        brokers=SimpleNamespace(),
        executions=SimpleNamespace(),
        cipher=SimpleNamespace(),
        gateway=SimpleNamespace(),
        clock=lambda: now,
    )

    with pytest.raises(ExecutionConflictError, match="bounded limit price"):
        await service.review(user_id="user-a", proposal_id=uuid4())
