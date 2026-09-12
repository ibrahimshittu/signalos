from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

import logfire

from signalos_backend.brokers.domain import BrokerEnvironment
from signalos_backend.brokers.service import BrokerService
from signalos_backend.brokers.store import BrokerStore
from signalos_backend.config import Settings, get_settings
from signalos_backend.db import IntelligenceStore, build_engine
from signalos_backend.execution.store import ExecutionStore
from signalos_backend.investment.agents import build_live_investment_agents
from signalos_backend.investment.pipeline import InvestmentPipeline
from signalos_backend.market.service import MarketService
from signalos_backend.market.sessions import SessionScheduler
from signalos_backend.market.store import MarketStore
from signalos_backend.notifications.gateway import ExpoPushGateway
from signalos_backend.notifications.service import NotificationService
from signalos_backend.notifications.store import NotificationStore
from signalos_backend.observability import configure_observability, flush_observability
from signalos_backend.proposals.service import ProposalService
from signalos_backend.proposals.store import ProposalStore
from signalos_backend.providers.bybit.client import BybitHttpGateway
from signalos_backend.security.credentials import CredentialCipher, UnavailableCredentialCipher
from signalos_backend.seeds import build_strategy_registry
from signalos_backend.users.memory import UserMemoryStore
from signalos_backend.users.store import UserStore

logger = logging.getLogger(__name__)


async def run_scan_loop(
    service: MarketService,
    *,
    environment: BrokerEnvironment,
    interval_seconds: int,
    pipeline: InvestmentPipeline | None = None,
    analysis_interval_seconds: int = 300,
    once: bool = False,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    last_analysis_at: datetime | None = None
    sessions = SessionScheduler()
    while True:
        analysis_requests = ()
        try:
            if pipeline is not None:
                analysis_requests = await service.claim_analysis_requests(
                    environment=environment,
                    limit=100,
                )
            scan = await service.run_scan(environment=environment)
            logger.info(
                "market scan completed scan_id=%s screened=%d liquid=%d shortlist=%d",
                scan.id,
                scan.source_count,
                len(scan.result.hot_universe),
                len(scan.result.agent_shortlist),
                extra={
                    "scan_id": scan.id,
                    "environment": environment.value,
                    "source_count": scan.source_count,
                    "shortlist_count": len(scan.result.agent_shortlist),
                },
            )
            logfire.info(
                "market scan completed",
                scan_id=scan.id,
                environment=environment.value,
                source_count=scan.source_count,
                liquid_count=len(scan.result.hot_universe),
                shortlist_count=len(scan.result.agent_shortlist),
            )
            due_sweeps = sessions.due_sweeps(
                scan.created_at,
                tolerance_seconds=min(interval_seconds // 2, 300),
            )
            analysis_due = pipeline is not None and (
                last_analysis_at is None
                or scan.created_at - last_analysis_at
                >= timedelta(seconds=analysis_interval_seconds)
                or bool(due_sweeps)
                or bool(analysis_requests)
            )
            if analysis_due and pipeline is not None:
                # Read operator governance at each analysis, not just process startup.
                durable_strategies, _ = await pipeline.intelligence_store.load_governance()
                for strategy in durable_strategies:
                    pipeline.strategies.restore(strategy.id, strategy)
                summary = await pipeline.analyze_scan(scan, session_sweeps=due_sweeps)
                last_analysis_at = scan.created_at
                logger.info(
                    (
                        "investment analysis completed scan_id=%s approved_strategies=%d "
                        "candidates=%d strategy_matches=%d signals=%d analyses=%d "
                        "no_trade=%d proposals=%d duplicates=%d gate_rejections=%d "
                        "model_available=%s"
                    ),
                    summary.scan_id,
                    summary.approved_strategies,
                    summary.candidates_considered,
                    summary.strategy_matches,
                    summary.signals_found,
                    summary.analysis_completed,
                    summary.no_trade_decisions,
                    summary.proposals_created,
                    summary.duplicates_skipped,
                    summary.gate_rejections,
                    summary.model_available,
                    extra=summary.model_dump(),
                )
                logfire.info("investment analysis completed", **summary.model_dump())
                if analysis_requests:
                    await service.complete_analysis_requests(
                        requests=analysis_requests,
                        scan_id=scan.id,
                    )
                    logfire.info(
                        "manual market analysis requests completed",
                        request_count=len(analysis_requests),
                        scan_id=scan.id,
                        environment=environment.value,
                    )
        except Exception:
            logger.exception("market scan failed", extra={"environment": environment.value})
            logfire.exception("market scan failed", environment=environment.value)
            if analysis_requests:
                await service.fail_analysis_requests(
                    requests=analysis_requests,
                    error_code="market_analysis_failed",
                )
            if once:
                raise
        if once:
            return
        await sleep(interval_seconds)


async def run_worker(
    settings: Settings,
    *,
    environment: BrokerEnvironment,
    once: bool,
) -> None:
    engine = build_engine(settings.database_url.get_secret_value())
    configure_observability(
        settings=settings,
        engine=engine,
        service_name="signalos-market-worker",
    )
    intelligence = IntelligenceStore(engine)
    users = UserStore(intelligence.sessions)
    brokers = BrokerStore(intelligence.sessions)
    memories = UserMemoryStore(intelligence.sessions)
    proposals = ProposalStore(intelligence.sessions)
    notifications = NotificationStore(intelligence.sessions)
    market_store = MarketStore(intelligence.sessions)
    execution_store = ExecutionStore(intelligence.sessions)
    gateway = BybitHttpGateway(
        mainnet_base_url=settings.bybit_mainnet_base_url,
        testnet_base_url=settings.bybit_testnet_base_url,
        recv_window_ms=settings.bybit_recv_window_ms,
        timeout_seconds=settings.bybit_timeout_seconds,
    )
    service = MarketService(
        store=market_store,
        gateway=gateway,
        max_data_age=timedelta(seconds=settings.market_data_max_age_seconds),
        instrument_refresh_interval=timedelta(seconds=settings.instrument_refresh_seconds),
    )
    if settings.credential_encryption_key is None:
        cipher = UnavailableCredentialCipher()
    else:
        cipher = CredentialCipher(
            (
                settings.credential_encryption_key.get_secret_value(),
                *(key.get_secret_value() for key in settings.credential_previous_encryption_keys),
            )
        )
    expo = ExpoPushGateway(
        access_token=(
            settings.expo_access_token.get_secret_value()
            if settings.expo_access_token is not None
            else "test-only"
        ),
        base_url=settings.expo_push_base_url,
    )
    notification_service = NotificationService(
        store=notifications,
        cipher=cipher,
        gateway=expo,
        users=users,
        proposals=proposals,
    )
    try:
        if settings.environment == "test":
            await intelligence.create_schema()
        strategy_registry = build_strategy_registry()
        durable_strategies, _ = await intelligence.load_governance()
        for strategy in durable_strategies:
            strategy_registry.restore(strategy.id, strategy)
        pipeline = InvestmentPipeline(
            market_store=market_store,
            market_gateway=gateway,
            intelligence_store=intelligence,
            strategies=strategy_registry,
            users=users,
            brokers=brokers,
            account_sync=BrokerService(
                settings=settings,
                store=brokers,
                cipher=cipher,
                bybit=gateway,
            ),
            position_store=execution_store,
            memories=memories,
            proposals=ProposalService(
                users=users,
                brokers=brokers,
                proposals=proposals,
                memories=memories,
                notifications=notification_service,
            ),
            proposal_store=proposals,
            agents=build_live_investment_agents(settings),
            max_candidates=settings.market_analysis_max_candidates,
            candle_interval_minutes=settings.market_analysis_candle_interval_minutes,
            candle_limit=settings.market_analysis_candle_limit,
            position_max_age=timedelta(
                seconds=max(
                    15,
                    settings.execution_reconciliation_interval_seconds * 3,
                )
            ),
        )
        await run_scan_loop(
            service,
            environment=environment,
            interval_seconds=settings.market_scan_interval_seconds,
            pipeline=pipeline,
            analysis_interval_seconds=settings.market_analysis_interval_seconds,
            once=once,
        )
    finally:
        await expo.close()
        await gateway.close()
        await engine.dispose()
        flush_observability()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Bybit scan-to-proposal pipeline")
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
