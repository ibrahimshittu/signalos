from __future__ import annotations

import base64
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from signalos_backend.brokers.domain import ActiveBrokerAccount, BrokerEnvironment
from signalos_backend.brokers.store import BrokerConnectionRecord
from signalos_backend.db import IntelligenceStore, build_engine
from signalos_backend.execution.domain import (
    BrokerExecutionSnapshot,
    BrokerOrderSnapshot,
    BrokerOrderState,
    BrokerPositionSnapshot,
    BrokerPositionState,
)
from signalos_backend.execution.reconciliation import ReconciliationService, map_order_state
from signalos_backend.execution.store import BrokerExecutionRecord, ExecutionStore
from signalos_backend.market.domain import MarketCategory
from signalos_backend.proposals.domain import OrderSide, OrderType
from signalos_backend.security.credentials import CredentialCipher


def test_bybit_order_states_map_to_durable_signalos_states() -> None:
    assert map_order_state("New") is BrokerOrderState.ACKNOWLEDGED
    assert map_order_state("PartiallyFilled") is BrokerOrderState.PARTIALLY_FILLED
    assert map_order_state("Filled") is BrokerOrderState.FILLED
    assert map_order_state("Cancelled") is BrokerOrderState.CANCELLED
    assert map_order_state("PartiallyFilledCanceled") is BrokerOrderState.CANCELLED
    assert map_order_state("Rejected") is BrokerOrderState.REJECTED
    assert map_order_state("unexpected") is BrokerOrderState.RECONCILIATION_REQUIRED


@pytest.mark.asyncio
async def test_reconciliation_reads_broker_truth_and_persists_each_stream() -> None:
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    connection_id = uuid4()
    account = ActiveBrokerAccount(
        user_id="user-a",
        connection_id=connection_id,
        environment=BrokerEnvironment.MAINNET,
    )
    cipher = CredentialCipher((base64.urlsafe_b64encode(b"r" * 32).decode(),))
    encrypted_key = cipher.encrypt("write-key")
    encrypted_secret = cipher.encrypt("write-secret")
    order = SimpleNamespace(
        id=uuid4(),
        broker_order_link_id="sos-order-1",
        category=MarketCategory.LINEAR,
    )
    order_snapshot = BrokerOrderSnapshot(
        order_id="order-1",
        order_link_id="sos-order-1",
        category=MarketCategory.LINEAR,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        status="PartiallyFilled",
        quantity=Decimal("0.02"),
        cumulative_executed_quantity=Decimal("0.01"),
        leaves_quantity=Decimal("0.01"),
        average_price=Decimal("68000"),
        updated_at=now,
    )
    execution = BrokerExecutionSnapshot(
        execution_id="execution-1",
        order_id="order-1",
        order_link_id="sos-order-1",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        price=Decimal("68000"),
        quantity=Decimal("0.01"),
        value=Decimal("680"),
        fee=Decimal("0.34"),
        executed_at=now,
    )
    position = BrokerPositionSnapshot(
        category=MarketCategory.LINEAR,
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
        updated_at=now,
    )

    class Brokers:
        async def list_active_accounts(self, *, environment):
            assert environment is BrokerEnvironment.MAINNET
            return (account,)

        async def get_credential_ciphertexts(self, **kwargs):
            assert kwargs["connection_id"] == connection_id
            return encrypted_key, encrypted_secret

    class Executions:
        def __init__(self) -> None:
            self.saved_order = None
            self.saved_executions = None
            self.saved_positions = None

        async def list_reconcilable_orders(self, **kwargs):
            assert kwargs["connection_id"] == connection_id
            return (order,)

        async def latest_execution_at(self, **kwargs):
            return None

        async def reconcile_order(self, **kwargs):
            self.saved_order = kwargs

        async def save_executions(self, **kwargs):
            self.saved_executions = kwargs

        async def replace_open_positions(self, **kwargs):
            self.saved_positions = kwargs

    class Gateway:
        async def get_order_snapshot(self, **kwargs):
            assert kwargs["api_key"] == "write-key"
            return order_snapshot

        async def get_executions(self, **kwargs):
            return (execution,) if kwargs["category"] == "linear" else ()

        async def get_positions(self, **kwargs):
            return (position,)

    executions = Executions()
    summary = await ReconciliationService(
        brokers=Brokers(),
        executions=executions,
        cipher=cipher,
        gateway=Gateway(),
        clock=lambda: now,
    ).run_once(environment=BrokerEnvironment.MAINNET)

    assert summary.accounts_reconciled == 1
    assert summary.orders_reconciled == 1
    assert summary.executions_seen == 1
    assert summary.open_positions == 1
    assert executions.saved_order["state"] is BrokerOrderState.PARTIALLY_FILLED
    assert executions.saved_executions["snapshots"] == (execution,)
    assert executions.saved_positions["snapshots"] == (position,)


@pytest.mark.asyncio
async def test_reconciled_positions_close_when_the_broker_no_longer_returns_them(tmp_path) -> None:
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    connection_id = uuid4()
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'positions.db'}")
    database = IntelligenceStore(engine)
    await database.create_schema()
    async with database.sessions() as session:
        session.add(
            BrokerConnectionRecord(
                id=str(connection_id),
                user_id="user-a",
                provider_id="bybit",
                environment=BrokerEnvironment.MAINNET.value,
                status="healthy",
                external_uid="123",
                parent_uid="0",
                permission_fingerprint="fingerprint",
                last_error_code=None,
                last_verified_at=now,
                last_synced_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    store = ExecutionStore(database.sessions)
    position = BrokerPositionSnapshot(
        category=MarketCategory.LINEAR,
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
        updated_at=now,
    )
    execution = BrokerExecutionSnapshot(
        execution_id="execution-1",
        order_id="order-1",
        order_link_id="external-order-link",
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        price=Decimal("68000"),
        quantity=Decimal("0.01"),
        value=Decimal("680"),
        fee=Decimal("0.34"),
        executed_at=now,
    )

    await store.replace_open_positions(
        user_id="user-a",
        connection_id=connection_id,
        environment=BrokerEnvironment.MAINNET,
        snapshots=(position,),
        reconciled_at=now,
    )
    await store.save_executions(
        user_id="user-a",
        connection_id=connection_id,
        environment=BrokerEnvironment.MAINNET,
        snapshots=(execution,),
    )
    await store.save_executions(
        user_id="user-a",
        connection_id=connection_id,
        environment=BrokerEnvironment.MAINNET,
        snapshots=(execution,),
    )

    open_positions = await store.list_positions(user_id="user-a")
    assert len(open_positions) == 1
    assert open_positions[0].state is BrokerPositionState.OPEN
    portfolio = await store.get_position_portfolio(user_id="user-a", connection_id=connection_id)
    assert portfolio is not None
    assert portfolio.positions == open_positions
    assert portfolio.reconciled_at == now
    assert await store.latest_execution_at(connection_id=connection_id) == now
    async with database.sessions() as session:
        count = await session.scalar(select(func.count()).select_from(BrokerExecutionRecord))
    assert count == 1

    await store.replace_open_positions(
        user_id="user-a",
        connection_id=connection_id,
        environment=BrokerEnvironment.MAINNET,
        snapshots=(),
        reconciled_at=now.replace(minute=1),
    )

    assert await store.list_positions(user_id="user-a") == ()
    closed = await store.list_positions(user_id="user-a", open_only=False)
    assert closed[0].state is BrokerPositionState.CLOSED
    assert closed[0].size == 0
    await engine.dispose()
