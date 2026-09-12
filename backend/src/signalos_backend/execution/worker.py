from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

import logfire

from signalos_backend.brokers.domain import BrokerEnvironment
from signalos_backend.brokers.store import BrokerStore
from signalos_backend.config import Settings, get_settings
from signalos_backend.db import IntelligenceStore, build_engine
from signalos_backend.execution.reconciliation import (
    ReconciliationService,
    ReconciliationSummary,
)
from signalos_backend.execution.store import ExecutionStore
from signalos_backend.observability import configure_observability, flush_observability
from signalos_backend.providers.bybit.client import BybitHttpGateway
from signalos_backend.security.credentials import CredentialCipher

logger = logging.getLogger(__name__)


class Reconciler(Protocol):
    async def run_once(self, *, environment: BrokerEnvironment) -> ReconciliationSummary: ...


async def run_reconciliation_loop(
    service: Reconciler,
    *,
    environment: BrokerEnvironment,
    interval_seconds: int,
    once: bool = False,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    while True:
        try:
            summary = await service.run_once(environment=environment)
        except Exception:
            logfire.exception("broker reconciliation cycle failed", environment=environment.value)
            logger.exception(
                "broker reconciliation cycle failed",
                extra={"environment": environment.value},
            )
            if once:
                raise
        else:
            logfire.info(
                "broker reconciliation completed",
                environment=environment.value,
                **summary.model_dump(),
            )
            logger.info(
                "broker reconciliation completed",
                extra={"environment": environment.value, **summary.model_dump()},
            )
        if once:
            return
        await sleep(interval_seconds)


async def run_worker(
    settings: Settings,
    *,
    environment: BrokerEnvironment,
    once: bool,
) -> None:
    if settings.credential_encryption_key is None:
        raise RuntimeError("broker reconciliation requires a credential encryption key")
    engine = build_engine(settings.database_url.get_secret_value())
    configure_observability(
        settings=settings, engine=engine, service_name="signalos-execution-worker"
    )
    database = IntelligenceStore(engine)
    gateway = BybitHttpGateway(
        mainnet_base_url=settings.bybit_mainnet_base_url,
        testnet_base_url=settings.bybit_testnet_base_url,
        recv_window_ms=settings.bybit_recv_window_ms,
        timeout_seconds=settings.bybit_timeout_seconds,
    )
    cipher = CredentialCipher(
        (
            settings.credential_encryption_key.get_secret_value(),
            *(key.get_secret_value() for key in settings.credential_previous_encryption_keys),
        )
    )
    service = ReconciliationService(
        brokers=BrokerStore(database.sessions),
        executions=ExecutionStore(database.sessions),
        cipher=cipher,
        gateway=gateway,
    )
    try:
        if settings.environment == "test":
            await database.create_schema()
        await run_reconciliation_loop(
            service,
            environment=environment,
            interval_seconds=settings.execution_reconciliation_interval_seconds,
            once=once,
        )
    finally:
        await gateway.close()
        await engine.dispose()
        flush_observability()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile Bybit orders, fills, and positions")
    parser.add_argument(
        "--environment",
        choices=[item.value for item in BrokerEnvironment],
        default=BrokerEnvironment.MAINNET.value,
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(
        run_worker(
            get_settings(),
            environment=BrokerEnvironment(args.environment),
            once=args.once,
        )
    )


if __name__ == "__main__":  # pragma: no cover
    main()
