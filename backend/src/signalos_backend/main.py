from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI

from signalos_backend.api.routes import router
from signalos_backend.api.studio_routes import router as studio_router
from signalos_backend.brokers.context import BrokerContextService
from signalos_backend.brokers.service import BrokerService
from signalos_backend.brokers.store import BrokerStore
from signalos_backend.config import Settings, get_settings
from signalos_backend.db import IntelligenceStore, build_engine
from signalos_backend.execution.service import ExecutionService
from signalos_backend.execution.store import ExecutionStore
from signalos_backend.identity import SupabaseAccessTokenVerifier
from signalos_backend.intelligence.agents import build_agents
from signalos_backend.intelligence.evidence import EvidenceGraph
from signalos_backend.intelligence.service import IntelligenceService
from signalos_backend.market.service import MarketService
from signalos_backend.market.store import MarketStore
from signalos_backend.notifications.gateway import ExpoPushGateway
from signalos_backend.notifications.service import NotificationService
from signalos_backend.notifications.store import NotificationStore
from signalos_backend.observability import configure_observability
from signalos_backend.proposals.service import ProposalService
from signalos_backend.proposals.store import ProposalStore
from signalos_backend.providers.bybit.client import BybitHttpGateway
from signalos_backend.security.credentials import CredentialCipher, UnavailableCredentialCipher
from signalos_backend.seeds import (
    build_skill_registry,
    build_strategy_registry,
    build_tool_registry,
)
from signalos_backend.studio import StudioServices
from signalos_backend.temporal.workflows import DeepResearchInput, DeepResearchWorkflow
from signalos_backend.users.memory import UserMemoryStore
from signalos_backend.users.personalization import build_personalization_generator
from signalos_backend.users.service import UserService
from signalos_backend.users.store import UserStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = build_engine(settings.database_url.get_secret_value())
    store = IntelligenceStore(engine)
    user_store = UserStore(store.sessions)
    memory_store = UserMemoryStore(store.sessions)
    broker_store = BrokerStore(store.sessions)
    market_store = MarketStore(store.sessions)
    proposal_store = ProposalStore(store.sessions)
    execution_store = ExecutionStore(store.sessions)
    notification_store = NotificationStore(store.sessions)
    live_bybit = BybitHttpGateway(
        mainnet_base_url=settings.bybit_mainnet_base_url,
        testnet_base_url=settings.bybit_testnet_base_url,
        recv_window_ms=settings.bybit_recv_window_ms,
        timeout_seconds=settings.bybit_timeout_seconds,
    )
    if settings.credential_encryption_key is None:
        credential_cipher = UnavailableCredentialCipher()
    else:
        credential_cipher = CredentialCipher(
            (
                settings.credential_encryption_key.get_secret_value(),
                *(key.get_secret_value() for key in settings.credential_previous_encryption_keys),
            )
        )
    broker_service = BrokerService(
        settings=settings,
        store=broker_store,
        cipher=credential_cipher,
        bybit=live_bybit,
    )
    expo_gateway = ExpoPushGateway(
        access_token=(
            settings.expo_access_token.get_secret_value()
            if settings.expo_access_token is not None
            else "test-only"
        ),
        base_url=settings.expo_push_base_url,
    )
    notification_service = NotificationService(
        store=notification_store,
        cipher=credential_cipher,
        gateway=expo_gateway,
        users=user_store,
        proposals=proposal_store,
    )
    access_token_verifier = (
        None if settings.environment == "test" else SupabaseAccessTokenVerifier(settings)
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.environment == "test":
            await store.create_schema()
        sources, claims = await store.load_evidence()
        app.state.service.evidence.restore(sources, claims)
        strategies, skills = await store.load_governance()
        for strategy in strategies:
            app.state.service.strategies.restore(strategy.id, strategy)
        for skill in skills:
            app.state.service.skills.restore(skill.stable_id, skill)
        app.state.service.agents = build_agents(settings, app.state.service.skills)
        if settings.temporal_enabled:
            from temporalio.client import Client

            temporal_client = await Client.connect(
                settings.temporal_address,
                namespace=settings.temporal_namespace,
            )

            async def dispatch(run_id):
                await temporal_client.start_workflow(
                    DeepResearchWorkflow.run,
                    DeepResearchInput(
                        run_id=str(run_id),
                        api_base_url=settings.api_base_url,
                        operator_key=settings.api_key.get_secret_value(),
                    ),
                    id=f"deep-research-{run_id}",
                    task_queue=settings.temporal_research_queue,
                )

            app.state.service.deep_dispatcher = dispatch
        yield
        if access_token_verifier is not None:
            await access_token_verifier.close()
        await expo_gateway.close()
        await live_bybit.close()
        await engine.dispose()

    app = FastAPI(
        title="SignalOS Finance Intelligence",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.access_token_verifier = access_token_verifier
    app.state.studio = StudioServices(
        users=UserService(
            users=user_store,
            brokers=broker_store,
            memories=memory_store,
            personalizer=build_personalization_generator(settings),
        ),
        brokers=broker_service,
        broker_contexts=BrokerContextService(store.sessions),
        markets=MarketService(
            store=market_store,
            gateway=live_bybit,
            max_data_age=timedelta(seconds=settings.market_data_max_age_seconds),
            instrument_refresh_interval=timedelta(seconds=settings.instrument_refresh_seconds),
        ),
        proposals=ProposalService(
            users=user_store,
            brokers=broker_store,
            proposals=proposal_store,
            memories=memory_store,
            notifications=notification_service,
        ),
        executions=ExecutionService(
            proposals=proposal_store,
            users=user_store,
            intelligence=store,
            brokers=broker_store,
            executions=execution_store,
            cipher=credential_cipher,
            gateway=live_bybit,
        ),
        notifications=notification_service,
    )
    app.state.service = IntelligenceService(
        settings=settings,
        store=store,
        evidence=EvidenceGraph(),
        strategies=build_strategy_registry(),
        skills=build_skill_registry(),
        tools=build_tool_registry(),
    )
    app.include_router(router)
    app.include_router(studio_router)

    if configure_observability(
        settings=settings,
        engine=engine,
        service_name="signalos-backend",
    ):
        import logfire

        logfire.instrument_fastapi(app)
    return app


app = create_app()
