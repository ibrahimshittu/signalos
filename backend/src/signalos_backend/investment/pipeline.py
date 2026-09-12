from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from signalos_backend.brokers.domain import (
    BrokerEnvironment,
    BrokerPolicyError,
    BrokerProviderError,
)
from signalos_backend.brokers.store import BrokerStore
from signalos_backend.db import IntelligenceStore
from signalos_backend.domain import StrategySpec, utc_now
from signalos_backend.execution.domain import PositionPortfolioSnapshot
from signalos_backend.execution.portfolio import position_portfolio_fingerprint
from signalos_backend.intelligence.registries import StrategyRegistry
from signalos_backend.investment.agents import DirectorDeps, PortfolioAdvisorDeps
from signalos_backend.investment.domain import (
    DecisionAction,
    InvestmentDecision,
    PortfolioAdvice,
    PortfolioPositionContext,
    PortfolioProfileContext,
)
from signalos_backend.investment.gates import GateInput, MandatoryGateEvaluator
from signalos_backend.investment.personalization import LearnedPreference
from signalos_backend.investment.sizing import (
    OpportunitySizingInput,
    OpportunitySizingPolicy,
    SizingRejected,
)
from signalos_backend.market.domain import (
    Candle,
    Instrument,
    MarketCategory,
    MarketReview,
    MarketReviewCandidate,
    MarketReviewStatus,
    MarketScan,
    PortfolioReviewOutcome,
    TickerSnapshot,
)
from signalos_backend.market.sessions import SessionScheduler, SessionSweep
from signalos_backend.market.signals import DeterministicSignalEngine, StrategySignal
from signalos_backend.market.store import MarketStore
from signalos_backend.proposals.domain import CreateTradeProposal, OrderSide, OrderType
from signalos_backend.proposals.service import ProposalService
from signalos_backend.proposals.store import ProposalStore
from signalos_backend.users.memory import MemoryKind, UserMemoryStore
from signalos_backend.users.store import UserStore


class InvestmentAnalysisAgent(Protocol):
    async def analyze(self, deps: DirectorDeps) -> InvestmentDecision: ...

    async def advise(self, deps: PortfolioAdvisorDeps) -> PortfolioAdvice: ...


class AccountSynchronizer(Protocol):
    async def sync(self, *, user_id: str, connection_id) -> object: ...


class PositionPortfolioStore(Protocol):
    async def get_position_portfolio(
        self, *, user_id: str, connection_id
    ) -> PositionPortfolioSnapshot | None: ...


class DeepMarketGateway(Protocol):
    async def get_closed_klines(
        self,
        *,
        environment: BrokerEnvironment,
        category: MarketCategory,
        symbol: str,
        interval_minutes: int,
        limit: int,
    ) -> tuple[Candle, ...]: ...

    async def get_max_leverage(
        self,
        *,
        environment: BrokerEnvironment,
        category: MarketCategory,
        symbol: str,
    ) -> Decimal: ...


class PipelineRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scan_id: str
    approved_strategies: int = Field(ge=0)
    candidates_considered: int = Field(ge=0)
    strategy_matches: int = Field(ge=0)
    signals_found: int = Field(ge=0)
    analysis_completed: int = Field(ge=0)
    no_trade_decisions: int = Field(ge=0)
    proposals_created: int = Field(ge=0)
    duplicates_skipped: int = Field(ge=0)
    gate_rejections: int = Field(ge=0)
    model_available: bool


class InvestmentPipeline:
    """Application-owned scan-to-proposal orchestration with no broker-write capability."""

    def __init__(
        self,
        *,
        market_store: MarketStore,
        market_gateway: DeepMarketGateway,
        intelligence_store: IntelligenceStore,
        strategies: StrategyRegistry,
        users: UserStore,
        brokers: BrokerStore,
        account_sync: AccountSynchronizer,
        position_store: PositionPortfolioStore,
        memories: UserMemoryStore,
        proposals: ProposalService,
        proposal_store: ProposalStore,
        agents: InvestmentAnalysisAgent | None,
        clock: Callable[[], datetime] = utc_now,
        max_candidates: int = 5,
        candle_interval_minutes: int = 15,
        candle_limit: int = 200,
        proposal_ttl: timedelta = timedelta(minutes=3),
        position_max_age: timedelta = timedelta(seconds=15),
    ) -> None:
        self.market_store = market_store
        self.market_gateway = market_gateway
        self.intelligence_store = intelligence_store
        self.strategies = strategies
        self.users = users
        self.brokers = brokers
        self.account_sync = account_sync
        self.position_store = position_store
        self.memories = memories
        self.proposals = proposals
        self.proposal_store = proposal_store
        self.agents = agents
        self.clock = clock
        self.max_candidates = max_candidates
        self.candle_interval_minutes = candle_interval_minutes
        self.candle_limit = candle_limit
        self.proposal_ttl = proposal_ttl
        self.position_max_age = position_max_age
        self.signal_engine = DeterministicSignalEngine()
        self.sizing = OpportunitySizingPolicy()
        self.gates = MandatoryGateEvaluator()
        self.sessions = SessionScheduler()

    async def analyze_scan(
        self, scan: MarketScan, *, session_sweeps: tuple[SessionSweep, ...] = ()
    ) -> PipelineRunSummary:
        counters = {
            "candidates_considered": 0,
            "strategy_matches": 0,
            "signals_found": 0,
            "analysis_completed": 0,
            "no_trade_decisions": 0,
            "proposals_created": 0,
            "duplicates_skipped": 0,
            "gate_rejections": 0,
        }
        approved = self.strategies.approved()
        if self.agents is None:
            summary = PipelineRunSummary(
                scan_id=scan.id,
                approved_strategies=len(approved),
                model_available=False,
                **counters,
            )
            await self._save_review(
                scan=scan,
                summary=summary,
                candidates=tuple(
                    MarketReviewCandidate(
                        category=candidate.category,
                        symbol=candidate.symbol,
                        rank=rank,
                        status=MarketReviewStatus.MODEL_UNAVAILABLE,
                        reason="AI analysis is temporarily unavailable.",
                    )
                    for rank, candidate in enumerate(
                        scan.result.agent_shortlist[: self.max_candidates], start=1
                    )
                ),
            )
            return summary

        reviews: list[MarketReviewCandidate] = []
        for rank, candidate in enumerate(
            scan.result.agent_shortlist[: self.max_candidates], start=1
        ):
            counters["candidates_considered"] += 1
            instrument = await self.market_store.get_instrument(
                environment=scan.environment,
                category=candidate.category,
                symbol=candidate.symbol,
            )
            ticker = await self.market_store.get_ticker(
                environment=scan.environment,
                category=candidate.category,
                symbol=candidate.symbol,
            )
            if instrument is None or ticker is None:
                reviews.append(
                    MarketReviewCandidate(
                        category=candidate.category,
                        symbol=candidate.symbol,
                        rank=rank,
                        status=MarketReviewStatus.MARKET_DATA_UNAVAILABLE,
                        reason="Required market details were unavailable for this review.",
                    )
                )
                continue
            strategy = self._select_strategy(approved, instrument)
            if strategy is None:
                catalog_available = bool(approved)
                reviews.append(
                    MarketReviewCandidate(
                        category=candidate.category,
                        symbol=candidate.symbol,
                        rank=rank,
                        status=(
                            MarketReviewStatus.NO_STRATEGY_MATCH
                            if catalog_available
                            else MarketReviewStatus.NO_APPROVED_STRATEGY
                        ),
                        reason=(
                            "No live strategy covers this market."
                            if catalog_available
                            else "No live strategy is available for trade analysis."
                        ),
                    )
                )
                continue
            counters["strategy_matches"] += 1
            evaluation = await self.intelligence_store.latest_evaluation(
                strategy.id, strategy.version
            )
            if (
                evaluation is None
                or not evaluation.passed_gates
                or f"evaluation:{evaluation.reproducibility_hash}"
                not in strategy.evidence_references
            ):
                counters["gate_rejections"] += 1
                reviews.append(
                    MarketReviewCandidate(
                        category=candidate.category,
                        symbol=candidate.symbol,
                        rank=rank,
                        status=MarketReviewStatus.EVIDENCE_GATE_REJECTED,
                        reason="The matched strategy has not passed its evidence checks.",
                        strategy_id=strategy.id,
                    )
                )
                continue
            candles = await self.market_gateway.get_closed_klines(
                environment=scan.environment,
                category=candidate.category,
                symbol=candidate.symbol,
                interval_minutes=self.candle_interval_minutes,
                limit=self.candle_limit,
            )
            signal = self.signal_engine.evaluate(
                strategy=strategy,
                candles=candles,
                ticker=ticker,
            )
            if signal is None:
                reviews.append(
                    MarketReviewCandidate(
                        category=candidate.category,
                        symbol=candidate.symbol,
                        rank=rank,
                        status=MarketReviewStatus.NO_VALID_SIGNAL,
                        reason="Completed candles did not form a valid setup.",
                        strategy_id=strategy.id,
                    )
                )
                continue
            counters["signals_found"] += 1
            decision = await self.agents.analyze(
                DirectorDeps(
                    candidate=candidate,
                    strategy_skill_id=strategy.family.value,
                    evidence_summary=self._evidence_summary(strategy, evaluation),
                    signal=signal,
                    session_sweeps=(
                        *session_sweeps,
                        *self._due_funding_sweeps(ticker, scan.created_at),
                    ),
                )
            )
            counters["analysis_completed"] += 1
            if (
                decision.candidate_symbol != candidate.symbol
                or decision.action is not DecisionAction.PROPOSE
            ):
                counters["no_trade_decisions"] += 1
                reviews.append(
                    MarketReviewCandidate(
                        category=candidate.category,
                        symbol=candidate.symbol,
                        rank=rank,
                        status=MarketReviewStatus.AI_NO_TRADE,
                        reason=self._bounded_reason(decision.opposing_case),
                        strategy_id=strategy.id,
                    )
                )
                continue
            created, duplicate, rejected = await self._personalize(
                scan_id=scan.id,
                environment=scan.environment,
                instrument=instrument,
                ticker=ticker,
                strategy=strategy,
                signal=signal,
                decision=decision,
                evaluation_passed=bool(evaluation and evaluation.passed_gates),
            )
            counters["proposals_created"] += created
            counters["duplicates_skipped"] += duplicate
            counters["gate_rejections"] += rejected
            reviews.append(
                MarketReviewCandidate(
                    category=candidate.category,
                    symbol=candidate.symbol,
                    rank=rank,
                    status=MarketReviewStatus.PASSED_MARKET_CHECKS,
                    reason=(
                        "Market checks passed; portfolio suitability determines whether this "
                        "becomes a proposal."
                    ),
                    strategy_id=strategy.id,
                )
            )

        summary = PipelineRunSummary(
            scan_id=scan.id,
            approved_strategies=len(approved),
            model_available=True,
            **counters,
        )
        await self._save_review(scan=scan, summary=summary, candidates=tuple(reviews))
        return summary

    async def _save_review(
        self,
        *,
        scan: MarketScan,
        summary: PipelineRunSummary,
        candidates: tuple[MarketReviewCandidate, ...],
    ) -> None:
        await self.market_store.save_review(
            MarketReview(
                scan_id=scan.id,
                environment=scan.environment,
                analyzed_at=self.clock().astimezone(UTC),
                candidates=candidates,
                **summary.model_dump(exclude={"scan_id"}),
            )
        )

    @staticmethod
    def _bounded_reason(reason: str) -> str:
        compact = " ".join(reason.split())
        if len(compact) <= 280:
            return compact
        return f"{compact[:277].rstrip()}..."

    async def _personalize(
        self,
        *,
        scan_id: str,
        environment: BrokerEnvironment,
        instrument: Instrument,
        ticker: TickerSnapshot,
        strategy: StrategySpec,
        signal: StrategySignal,
        decision: InvestmentDecision,
        evaluation_passed: bool,
    ) -> tuple[int, int, int]:
        created = duplicates = rejected = 0
        now = self.clock().astimezone(UTC)
        broker_max_leverage = await self.market_gateway.get_max_leverage(
            environment=environment,
            category=instrument.category,
            symbol=instrument.symbol,
        )
        for account in await self.brokers.list_active_accounts(environment=environment):

            async def record_outcome(code: str, reason: str, *, account=account) -> None:
                await self.market_store.save_portfolio_review(
                    user_id=account.user_id,
                    connection_id=account.connection_id,
                    scan_id=scan_id,
                    category=instrument.category,
                    symbol=instrument.symbol,
                    outcome=PortfolioReviewOutcome(
                        code=code,
                        reason=self._bounded_reason(reason),
                        evaluated_at=now,
                    ),
                )

            connection = await self.brokers.get_connection(
                user_id=account.user_id,
                connection_id=account.connection_id,
            )
            category_enabled = connection is not None and (
                (instrument.category is MarketCategory.SPOT and connection.spot_trading_enabled)
                or (
                    instrument.category is MarketCategory.LINEAR
                    and connection.derivatives_trading_enabled
                )
            )
            if not category_enabled:
                await record_outcome(
                    "permission_missing", "Your connected key does not permit this market category."
                )
                rejected += 1
                continue
            if await self.proposal_store.has_active(
                user_id=account.user_id,
                connection_id=account.connection_id,
                strategy_id=strategy.id,
                strategy_version=strategy.version,
                symbol=instrument.symbol,
                now=now,
            ):
                duplicates += 1
                await record_outcome(
                    "already_proposed",
                    "An active proposal or order already exists for this setup. "
                    "Open Signals to review it.",
                )
                continue
            profile = await self.users.get_profile(account.user_id)
            try:
                await self.account_sync.sync(
                    user_id=account.user_id,
                    connection_id=account.connection_id,
                )
            except (BrokerPolicyError, BrokerProviderError, KeyError):
                await record_outcome(
                    "account_sync_failed",
                    "Your account could not be refreshed. Check the connection and sync again.",
                )
                rejected += 1
                continue
            portfolio = await self.brokers.get_portfolio_summary(user_id=account.user_id)
            if (
                profile is None
                or portfolio is None
                or portfolio.connection_id != account.connection_id
                or not profile.disclosures_accepted
            ):
                await record_outcome(
                    "profile_incomplete",
                    "An accepted profile and current account balances are required. "
                    "Check Account to complete setup.",
                )
                rejected += 1
                continue
            position_portfolio = await self.position_store.get_position_portfolio(
                user_id=account.user_id,
                connection_id=account.connection_id,
            )
            if (
                position_portfolio is None
                or now - position_portfolio.reconciled_at > self.position_max_age
            ):
                await record_outcome(
                    "positions_stale",
                    "Your positions have not been reconciled recently enough to size this trade. "
                    "The execution worker must refresh them.",
                )
                rejected += 1
                continue
            if (
                instrument.category is MarketCategory.LINEAR
                and not profile.adaptive_mandate.derivatives_eligible
            ):
                await record_outcome(
                    "mandate_spot_only",
                    "Your current safety limits allow spot only; this candidate is a derivative. "
                    "Review your answers in Account if they changed.",
                )
                rejected += 1
                continue
            preferences = await self._learned_preferences(account.user_id)
            personalized_policy = await self.users.get_personalized_policy(account.user_id)
            if any(
                preference.is_active
                and preference.key == "avoid_strategy_family"
                and preference.value == strategy.family.value
                for preference in preferences
            ):
                await record_outcome(
                    "learned_preference",
                    "This strategy family is excluded by your learned preferences. "
                    "You can reset those preferences in Account.",
                )
                rejected += 1
                continue

            entry, stop, target = self._rounded_levels(signal, instrument)
            funding_bps = abs(ticker.funding_rate or Decimal("0")) * Decimal("10000")
            cost_bps = (
                strategy.cost_model.fee_bps
                + strategy.cost_model.spread_bps
                + strategy.cost_model.slippage_bps
                + funding_bps
            )
            position_context = tuple(
                PortfolioPositionContext(
                    category=position.category.value,
                    symbol=position.symbol,
                    side=position.side.value,
                    size=position.size,
                    position_value=position.position_value,
                    leverage=position.leverage,
                    average_price=position.average_price,
                    mark_price=position.mark_price,
                    unrealised_pnl=position.unrealised_pnl,
                )
                for position in position_portfolio.positions
            )
            advice = await self.agents.advise(
                PortfolioAdvisorDeps(
                    profile=PortfolioProfileContext(
                        goals=tuple(goal.value for goal in profile.goals),
                        time_horizon=profile.time_horizon.value,
                        liquidity_need=profile.liquidity_need.value,
                        investing_experience=profile.investing_experience.value,
                        trading_experience=profile.trading_experience.value,
                        products_traded=tuple(product.value for product in profile.products_traded),
                        decision_frequency=profile.decision_frequency.value,
                        drawdown_response=profile.drawdown_response.value,
                        holding_periods=tuple(
                            holding_period.value for holding_period in profile.holding_periods
                        ),
                        explanation_detail=profile.explanation_detail.value,
                        risk_posture=profile.adaptive_mandate.risk_posture,
                        max_loss_per_trade_pct=(profile.adaptive_mandate.max_loss_per_trade_pct),
                        max_leverage=profile.adaptive_mandate.max_leverage,
                        derivatives_eligible=(profile.adaptive_mandate.derivatives_eligible),
                        personalization_source=(
                            personalized_policy.source if personalized_policy else None
                        ),
                        personalization_summary=(
                            personalized_policy.preferences.investor_summary
                            if personalized_policy
                            else None
                        ),
                        preferred_markets=(
                            tuple(
                                item.value
                                for item in personalized_policy.preferences.preferred_markets
                            )
                            if personalized_policy
                            else ()
                        ),
                        preferred_strategy_families=(
                            tuple(
                                item.value
                                for item in (
                                    personalized_policy.preferences.preferred_strategy_families
                                )
                            )
                            if personalized_policy
                            else ()
                        ),
                        preferred_sessions=(
                            tuple(
                                item.value
                                for item in personalized_policy.preferences.preferred_sessions
                            )
                            if personalized_policy
                            else ()
                        ),
                        avoid_conditions=(
                            personalized_policy.preferences.avoid_conditions
                            if personalized_policy
                            else ()
                        ),
                    ),
                    account_equity=portfolio.total_equity,
                    available_balance=portfolio.available_balance,
                    positions=position_context,
                    learned_preferences=preferences,
                    decision=decision,
                    signal=signal,
                )
            )
            if not advice.suitable:
                await record_outcome("portfolio_unsuitable", advice.why_reject)
                rejected += 1
                continue
            gross_exposure = sum(
                (position.position_value for position in position_portfolio.positions),
                start=Decimal("0"),
            )
            correlated_exposure = sum(
                (
                    position.position_value
                    for position in position_portfolio.positions
                    if position.side is signal.side
                ),
                start=Decimal("0"),
            )
            correlation = (
                min(correlated_exposure / portfolio.total_equity, Decimal("1"))
                if portfolio.total_equity > 0
                else Decimal("1")
            )
            try:
                sizing = self.sizing.size(
                    OpportunitySizingInput(
                        category=instrument.category,
                        side=signal.side,
                        entry_price=entry,
                        stop_loss=stop,
                        take_profit=target,
                        account_equity=portfolio.total_equity,
                        available_balance=portfolio.available_balance,
                        current_gross_exposure=gross_exposure,
                        correlated_exposure_pct=correlation,
                        max_loss_per_trade_pct=(profile.adaptive_mandate.max_loss_per_trade_pct),
                        mandate_max_leverage=profile.adaptive_mandate.max_leverage,
                        broker_max_leverage=broker_max_leverage,
                        agent_requested_leverage=min(
                            decision.requested_leverage,
                            signal.suggested_leverage,
                            advice.leverage_ceiling,
                        ),
                        agent_confidence=(decision.confidence * advice.confidence_multiplier),
                        quantity_step=instrument.quantity_step,
                        minimum_order_quantity=instrument.minimum_order_quantity,
                        minimum_notional=instrument.minimum_notional,
                        round_trip_cost_bps=cost_bps,
                    )
                )
            except (SizingRejected, ValueError) as exc:
                await record_outcome("sizing_rejected", str(exc))
                rejected += 1
                continue
            gate_report = self.gates.evaluate(
                GateInput(
                    strategy_status=strategy.status.value,
                    backtest_passed=evaluation_passed,
                    evidence_replicated=(evaluation_passed and bool(strategy.evidence_references)),
                    portfolio_risk_passed=True,
                    market_observed_at=signal.market_observed_at,
                    evaluated_at=now,
                )
            )
            if not gate_report.passed:
                await record_outcome("safety_gate_rejected", ", ".join(gate_report.failures))
                rejected += 1
                continue

            notional = sizing.notional
            fee = notional * strategy.cost_model.fee_bps / Decimal("10000")
            slippage = (
                notional
                * (strategy.cost_model.spread_bps + strategy.cost_model.slippage_bps)
                / Decimal("10000")
            )
            funding = notional * funding_bps / Decimal("10000")
            await self.proposals.create(
                user_id=account.user_id,
                payload=CreateTradeProposal(
                    connection_id=account.connection_id,
                    strategy_id=strategy.id,
                    strategy_version=strategy.version,
                    strategy_family=strategy.family.value,
                    category=instrument.category,
                    symbol=instrument.symbol,
                    side=signal.side,
                    order_type=OrderType.LIMIT,
                    quantity=sizing.quantity,
                    limit_price=entry,
                    stop_loss=stop,
                    take_profit=target,
                    leverage=sizing.leverage,
                    estimated_fees=fee,
                    estimated_funding=funding,
                    estimated_slippage=slippage,
                    estimated_max_loss=sizing.estimated_max_loss,
                    required_margin=sizing.required_margin,
                    portfolio_fingerprint=position_portfolio_fingerprint(
                        position_portfolio.positions
                    ),
                    position_reconciled_at=position_portfolio.reconciled_at,
                    market_price=signal.entry_price,
                    market_observed_at=signal.market_observed_at,
                    expires_at=now + self.proposal_ttl,
                    thesis=decision.thesis,
                    opposing_case=decision.opposing_case,
                    why_it_fits=advice.why_it_fits,
                    why_reject=advice.why_reject,
                    gate_report=gate_report,
                ),
            )
            created += 1
            await record_outcome(
                "proposed",
                "This setup passed your portfolio checks. "
                "Open the proposal in Signals to review its exact terms.",
            )
        return created, duplicates, rejected

    async def _learned_preferences(self, user_id: str) -> tuple[LearnedPreference, ...]:
        memories = await self.memories.list(user_id=user_id, limit=1_000)
        return tuple(
            LearnedPreference(
                key=memory.key,
                value=str(memory.value.get("value", "")),
                confidence=memory.confidence,
                evidence_count=memory.evidence_count,
            )
            for memory in memories
            if memory.kind is MemoryKind.LEARNED_PREFERENCE and memory.value.get("value")
        )

    @staticmethod
    def _select_strategy(
        strategies: list[StrategySpec], instrument: Instrument
    ) -> StrategySpec | None:
        for strategy in strategies:
            universe = set(strategy.eligible_universe)
            if instrument.symbol in universe or instrument.base_coin in universe:
                return strategy
        return None

    @staticmethod
    def _evidence_summary(strategy: StrategySpec, evaluation) -> str:
        if evaluation is None:
            return "No deterministic replication record is available."
        state = "passed" if evaluation.passed_gates else "failed"
        return (
            f"Deterministic replication {state}; reproducibility hash "
            f"{evaluation.reproducibility_hash}; evidence references "
            f"{', '.join(strategy.evidence_references) or 'none'}."
        )

    def _due_funding_sweeps(self, ticker: TickerSnapshot, at: datetime) -> tuple[SessionSweep, ...]:
        if ticker.next_funding_at is None:
            return ()
        return tuple(
            sweep
            for sweep in self.sessions.funding_sweeps(ticker.symbol, ticker.next_funding_at)
            if abs(sweep.scheduled_at - at.astimezone(UTC)) <= timedelta(seconds=30)
        )

    @staticmethod
    def _rounded_levels(
        signal: StrategySignal, instrument: Instrument
    ) -> tuple[Decimal, Decimal, Decimal]:
        step = instrument.tick_size

        def floor(value: Decimal) -> Decimal:
            return (value / step).to_integral_value(rounding=ROUND_DOWN) * step

        def ceiling(value: Decimal) -> Decimal:
            return (value / step).to_integral_value(rounding=ROUND_CEILING) * step

        entry = floor(signal.entry_price)
        if signal.side is OrderSide.BUY:
            return entry, floor(signal.stop_loss), floor(signal.take_profit)
        return entry, ceiling(signal.stop_loss), ceiling(signal.take_profit)
