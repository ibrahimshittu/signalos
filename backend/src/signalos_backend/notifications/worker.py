from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Awaitable, Callable

import logfire

from signalos_backend.config import Settings, get_settings
from signalos_backend.db import IntelligenceStore, build_engine
from signalos_backend.notifications.gateway import ExpoPushGateway
from signalos_backend.notifications.service import NotificationService
from signalos_backend.notifications.store import NotificationStore
from signalos_backend.observability import configure_observability, flush_observability
from signalos_backend.proposals.store import ProposalStore
from signalos_backend.security.credentials import CredentialCipher
from signalos_backend.users.store import UserStore

logger = logging.getLogger(__name__)


async def run_receipt_loop(
    service: NotificationService,
    *,
    interval_seconds: int,
    once: bool = False,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    while True:
        try:
            retried = await service.retry_failed()
            updated = await service.reconcile_receipts()
            logfire.info(
                "Expo deliveries reconciled", receipt_count=updated, retry_count=retried
            )
            logger.info(
                "Expo deliveries reconciled",
                extra={"receipt_count": updated, "retry_count": retried},
            )
        except Exception:
            logfire.exception("Expo receipt reconciliation failed")
            logger.exception("Expo receipt reconciliation failed")
            if once:
                raise
        if once:
            return
        await sleep(interval_seconds)


async def run_worker(settings: Settings, *, once: bool) -> None:
    if settings.credential_encryption_key is None or settings.expo_access_token is None:
        raise RuntimeError("notification worker requires encryption and Expo access tokens")
    engine = build_engine(settings.database_url.get_secret_value())
    configure_observability(
        settings=settings, engine=engine, service_name="signalos-notification-worker"
    )
    intelligence = IntelligenceStore(engine)
    gateway = ExpoPushGateway(
        access_token=settings.expo_access_token.get_secret_value(),
        base_url=settings.expo_push_base_url,
    )
    cipher = CredentialCipher(
        (
            settings.credential_encryption_key.get_secret_value(),
            *(key.get_secret_value() for key in settings.credential_previous_encryption_keys),
        )
    )
    service = NotificationService(
        store=NotificationStore(intelligence.sessions),
        cipher=cipher,
        gateway=gateway,
        users=UserStore(intelligence.sessions),
        proposals=ProposalStore(intelligence.sessions),
    )
    try:
        await run_receipt_loop(
            service,
            interval_seconds=settings.expo_receipt_interval_seconds,
            once=once,
        )
    finally:
        await gateway.close()
        await engine.dispose()
        flush_observability()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile SignalOS Expo push receipts")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker(get_settings(), once=args.once))


if __name__ == "__main__":  # pragma: no cover
    main()
