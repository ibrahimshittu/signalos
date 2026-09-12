from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
from signalos_backend.investment.gates import MandatoryGateReport
from signalos_backend.proposals.domain import (
    CreateTradeProposal,
    OrderSide,
    OrderType,
    ProposalStatus,
)
from signalos_backend.proposals.service import ProposalService
from signalos_backend.proposals.store import ProposalStore
from signalos_backend.security.credentials import CredentialCipher
from signalos_backend.users.domain import InvestmentProfileInput
from signalos_backend.users.store import UserStore


class FakeBybit:
    async def get_key_info(self, *, api_key, api_secret, environment):
        del api_secret, environment
        return BybitKeyInfo(
            user_id="123",
            parent_uid="0",
            is_master=True,
            read_only=False,
            ips=("203.0.113.10",),
            permissions=({"ContractTrade": ("Order", "Position"), "Wallet": ()}),
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


def profile() -> InvestmentProfileInput:
    return InvestmentProfileInput(
        goals=("capital_growth",),
        # Legacy clients may still send this planning value. It must not cap a
        # proposal below the synchronized account equity.
        intended_capital=Decimal("100"),
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
async def test_connected_account_can_receive_a_reviewable_proposal(tmp_path):
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'proposal.db'}")
    intelligence_store = IntelligenceStore(engine)
    user_store = UserStore(intelligence_store.sessions)
    broker_store = BrokerStore(intelligence_store.sessions)
    proposal_store = ProposalStore(intelligence_store.sessions)
    await intelligence_store.create_schema()
    await user_store.save_profile("user-a", profile())

    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'proposal.db'}",
    )
    cipher = CredentialCipher(
        (base64.urlsafe_b64encode(b"proposal-test-key-material-00000").decode(),)
    )
    brokers = BrokerService(settings, broker_store, cipher, FakeBybit())
    connection = await brokers.create(
        user_id="user-a",
        payload=CreateBrokerConnection(
            provider_id="bybit",
            environment=BrokerEnvironment.MAINNET,
            api_key="read-key",
            api_secret="read-secret",
        ),
    )
    await brokers.verify(user_id="user-a", connection_id=connection.id)
    await brokers.sync(user_id="user-a", connection_id=connection.id)

    service = ProposalService(
        users=user_store,
        brokers=broker_store,
        proposals=proposal_store,
        clock=lambda: now,
    )
    proposal = await service.create(
        user_id="user-a",
        payload=CreateTradeProposal(
            connection_id=connection.id,
            strategy_id="session-opening-breakout",
            strategy_version="1.0.0",
            strategy_family="session_opening",
            category="linear",
            symbol="ETHUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.20"),
            limit_price=Decimal("4200"),
            stop_loss=Decimal("4150"),
            take_profit=Decimal("4350"),
            leverage=Decimal("2"),
            estimated_fees=Decimal("1.20"),
            estimated_funding=Decimal("0.30"),
            estimated_slippage=Decimal("0.80"),
            estimated_max_loss=Decimal("12"),
            market_price=Decimal("4202"),
            market_observed_at=now - timedelta(seconds=20),
            expires_at=now + timedelta(minutes=2),
            thesis="Opening range was reclaimed with strong relative strength.",
            opposing_case="A failed reclaim would invalidate the setup quickly.",
            why_it_fits="Fits the user's swing horizon and explicit loss ceiling.",
            why_reject="Reject if short-term volatility is uncomfortable.",
            gate_report=MandatoryGateReport(passed=True, failures=()),
        ),
    )
    assert proposal.status is ProposalStatus.AVAILABLE
    assert proposal.connection_id == connection.id
    assert connection.credential_purposes == ("broker_access",)
    assert await proposal_store.get(user_id="user-a", proposal_id=proposal.id) == proposal
    assert await service.list(user_id="user-a", connection_id=connection.id) == (proposal,)
    assert await service.list(user_id="user-a", connection_id=proposal.id) == ()
    assert await service.list(user_id="user-b", connection_id=connection.id) == ()

    await engine.dispose()


@pytest.mark.asyncio
async def test_proposal_policy_rejects_failed_gates_before_persistence(tmp_path):
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'rejected.db'}")
    intelligence_store = IntelligenceStore(engine)
    await intelligence_store.create_schema()
    service = ProposalService(
        users=UserStore(intelligence_store.sessions),
        brokers=BrokerStore(intelligence_store.sessions),
        proposals=ProposalStore(intelligence_store.sessions),
    )

    with pytest.raises(ValueError, match="mandatory gates did not pass"):
        await service.create(
            user_id="user-a",
            payload=CreateTradeProposal.model_construct(
                gate_report=MandatoryGateReport(passed=False, failures=("evidence_not_replicated",))
            ),
        )

    await engine.dispose()
