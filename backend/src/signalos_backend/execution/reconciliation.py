from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from signalos_backend.brokers.domain import (
    ActiveBrokerAccount,
    BrokerCredentialPurpose,
    BrokerEnvironment,
)
from signalos_backend.domain import utc_now
from signalos_backend.execution.domain import (
    BrokerExecutionSnapshot,
    BrokerOrder,
    BrokerOrderSnapshot,
    BrokerOrderState,
    BrokerPositionSnapshot,
)
from signalos_backend.market.domain import MarketCategory
from signalos_backend.security.credentials import CredentialCipher

logger = logging.getLogger(__name__)


class ReconciliationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accounts_reconciled: int = Field(ge=0)
    accounts_failed: int = Field(ge=0)
    orders_reconciled: int = Field(ge=0)
    executions_seen: int = Field(ge=0)
    open_positions: int = Field(ge=0)


class ReconciliationBrokerStore(Protocol):
    async def list_active_accounts(
        self, *, environment: BrokerEnvironment
    ) -> tuple[ActiveBrokerAccount, ...]: ...

    async def get_credential_ciphertexts(
        self,
        *,
        user_id: str,
        connection_id: UUID,
        purpose: BrokerCredentialPurpose,
    ) -> tuple[str, str] | None: ...


class ReconciliationStore(Protocol):
    async def list_reconcilable_orders(self, *, connection_id: UUID) -> tuple[BrokerOrder, ...]: ...

    async def latest_execution_at(self, *, connection_id: UUID) -> datetime | None: ...

    async def reconcile_order(
        self,
        *,
        order_id: UUID,
        snapshot: BrokerOrderSnapshot,
        state: BrokerOrderState,
        reconciled_at: datetime,
    ) -> None: ...

    async def save_executions(
        self,
        *,
        user_id: str,
        connection_id: UUID,
        environment: BrokerEnvironment,
        snapshots: tuple[BrokerExecutionSnapshot, ...],
    ) -> None: ...

    async def replace_open_positions(
        self,
        *,
        user_id: str,
        connection_id: UUID,
        environment: BrokerEnvironment,
        snapshots: tuple[BrokerPositionSnapshot, ...],
        reconciled_at: datetime,
    ) -> None: ...


class ReconciliationGateway(Protocol):
    async def get_order_snapshot(self, **kwargs) -> BrokerOrderSnapshot | None: ...

    async def get_executions(self, **kwargs) -> tuple[BrokerExecutionSnapshot, ...]: ...

    async def get_positions(self, **kwargs) -> tuple[BrokerPositionSnapshot, ...]: ...


_ORDER_STATE_MAP = {
    "Created": BrokerOrderState.ACKNOWLEDGED,
    "New": BrokerOrderState.ACKNOWLEDGED,
    "Untriggered": BrokerOrderState.ACKNOWLEDGED,
    "Triggered": BrokerOrderState.ACKNOWLEDGED,
    "PartiallyFilled": BrokerOrderState.PARTIALLY_FILLED,
    "Filled": BrokerOrderState.FILLED,
    "Cancelled": BrokerOrderState.CANCELLED,
    "PartiallyFilledCanceled": BrokerOrderState.CANCELLED,
    "Deactivated": BrokerOrderState.CANCELLED,
    "Rejected": BrokerOrderState.REJECTED,
}


def map_order_state(broker_status: str) -> BrokerOrderState:
    return _ORDER_STATE_MAP.get(broker_status, BrokerOrderState.RECONCILIATION_REQUIRED)


class ReconciliationService:
    """Poll Bybit truth into durable state; acknowledgements are never treated as fills."""

    def __init__(
        self,
        *,
        brokers: ReconciliationBrokerStore,
        executions: ReconciliationStore,
        cipher: CredentialCipher,
        gateway: ReconciliationGateway,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.brokers = brokers
        self.executions = executions
        self.cipher = cipher
        self.gateway = gateway
        self.clock = clock

    async def run_once(self, *, environment: BrokerEnvironment) -> ReconciliationSummary:
        accounts = await self.brokers.list_active_accounts(environment=environment)
        reconciled = failed = orders_count = executions_count = positions_count = 0
        for account in accounts:
            try:
                account_counts = await self._reconcile_account(account)
            except Exception:  # worker records the failed account and continues with other users
                logger.exception(
                    "broker account reconciliation failed",
                    extra={
                        "connection_id": str(account.connection_id),
                        "environment": account.environment.value,
                    },
                )
                failed += 1
                continue
            reconciled += 1
            orders_count += account_counts[0]
            executions_count += account_counts[1]
            positions_count += account_counts[2]
        return ReconciliationSummary(
            accounts_reconciled=reconciled,
            accounts_failed=failed,
            orders_reconciled=orders_count,
            executions_seen=executions_count,
            open_positions=positions_count,
        )

    async def _reconcile_account(self, account: ActiveBrokerAccount) -> tuple[int, int, int]:
        encrypted = await self.brokers.get_credential_ciphertexts(
            user_id=account.user_id,
            connection_id=account.connection_id,
            purpose=BrokerCredentialPurpose.BROKER_ACCESS,
        )
        if encrypted is None:
            raise RuntimeError("broker credential is unavailable")
        api_key = self.cipher.decrypt(encrypted[0])
        api_secret = self.cipher.decrypt(encrypted[1])
        now = self.clock().astimezone(UTC)

        orders = await self.executions.list_reconcilable_orders(connection_id=account.connection_id)
        order_count = 0
        for order in orders:
            if order.category is None:
                continue
            snapshot = await self.gateway.get_order_snapshot(
                api_key=api_key,
                api_secret=api_secret,
                environment=account.environment,
                category=order.category.value,
                order_link_id=order.broker_order_link_id,
            )
            if snapshot is None:
                continue
            await self.executions.reconcile_order(
                order_id=order.id,
                snapshot=snapshot,
                state=map_order_state(snapshot.status),
                reconciled_at=now,
            )
            order_count += 1

        latest_execution = await self.executions.latest_execution_at(
            connection_id=account.connection_id
        )
        earliest = now - timedelta(days=7)
        start = max(
            earliest,
            (latest_execution - timedelta(seconds=60))
            if latest_execution is not None
            else now - timedelta(hours=24),
        )
        execution_pages = []
        for category in (MarketCategory.SPOT, MarketCategory.LINEAR):
            execution_pages.append(
                await self.gateway.get_executions(
                    api_key=api_key,
                    api_secret=api_secret,
                    environment=account.environment,
                    category=category.value,
                    start_time_ms=int(start.timestamp() * 1_000),
                )
            )
        executions = tuple(execution for page in execution_pages for execution in page)
        await self.executions.save_executions(
            user_id=account.user_id,
            connection_id=account.connection_id,
            environment=account.environment,
            snapshots=executions,
        )

        positions = await self.gateway.get_positions(
            api_key=api_key,
            api_secret=api_secret,
            environment=account.environment,
            category=MarketCategory.LINEAR.value,
            settle_coin="USDT",
        )
        await self.executions.replace_open_positions(
            user_id=account.user_id,
            connection_id=account.connection_id,
            environment=account.environment,
            snapshots=positions,
            reconciled_at=now,
        )
        return order_count, len(executions), len(positions)
