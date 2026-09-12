from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic_ai import Agent, RunContext, UsageLimits

from signalos_backend.config import Settings
from signalos_backend.investment.domain import (
    BearCase,
    BullCase,
    InvestmentDecision,
    MicrostructureAssessment,
    PortfolioAdvice,
    PortfolioPositionContext,
    PortfolioProfileContext,
    RegimeAssessment,
    SessionAssessment,
    StrategyAssessment,
)
from signalos_backend.investment.personalization import LearnedPreference
from signalos_backend.market.domain import MarketCandidate
from signalos_backend.market.sessions import SessionSweep
from signalos_backend.market.signals import StrategySignal


@dataclass(frozen=True)
class DirectorDeps:
    candidate: MarketCandidate
    strategy_skill_id: str
    evidence_summary: str
    signal: StrategySignal | None = None
    session_sweeps: tuple[SessionSweep, ...] = ()


@dataclass(frozen=True)
class PortfolioAdvisorDeps:
    profile: PortfolioProfileContext
    account_equity: Decimal
    available_balance: Decimal
    positions: tuple[PortfolioPositionContext, ...]
    learned_preferences: tuple[LearnedPreference, ...]
    decision: InvestmentDecision
    signal: StrategySignal


@dataclass(frozen=True)
class InvestmentAgentSet:
    director: Agent[DirectorDeps, InvestmentDecision]
    portfolio_advisor: Agent[PortfolioAdvisorDeps, PortfolioAdvice]

    async def analyze(self, deps: DirectorDeps) -> InvestmentDecision:
        result = await self.director.run(
            (
                "Analyze the supplied deterministic candidate. Delegate to relevant specialists, "
                "represent both supporting and opposing cases, and return no_trade when evidence "
                "is insufficient. Return calibrated confidence and requested leverage between 1 "
                "and 20, but never alter deterministic price levels or sizing. Your output is "
                "analysis only; application gates decide whether a proposal may be created."
            ),
            deps=deps,
            usage_limits=UsageLimits(
                request_limit=12,
                tool_calls_limit=6,
                output_tokens_limit=4_000,
            ),
        )
        return result.output

    async def advise(self, deps: PortfolioAdvisorDeps) -> PortfolioAdvice:
        result = await self.portfolio_advisor.run(
            (
                "Assess whether this already evidence-gated market opportunity fits this one "
                "user's explicit profile and current portfolio. You may reject it or reduce "
                "confidence/leverage. Never increase a hard limit, alter order levels, or "
                "authorize a trade. Explain both why it may fit and why the user may reject it."
            ),
            deps=deps,
            usage_limits=UsageLimits(
                request_limit=2,
                tool_calls_limit=0,
                output_tokens_limit=1_500,
            ),
        )
        return result.output


def build_investment_agents(*, director_model: Any, specialist_model: Any) -> InvestmentAgentSet:
    """Build an orchestrator that delegates through explicit read-only typed tools.

    Delegated runs share the parent usage object as required by Pydantic AI's documented
    multi-agent pattern:
    https://pydantic.dev/docs/ai/guides/multi-agent-applications/#agent-delegation
    """

    session_agent = Agent(
        specialist_model,
        name="session_analyst",
        output_type=SessionAssessment,
        instructions=(
            "Analyze session timing, prior-session range, opening range, sweeps, reclaims, and "
            "volume context. Treat session openings as activity windows, never trade triggers."
        ),
    )
    regime_agent = Agent(
        specialist_model,
        name="regime_analyst",
        output_type=RegimeAssessment,
        instructions="Classify trend, range, volatility, liquidity, and correlation regime.",
    )
    strategy_agent = Agent(
        specialist_model,
        name="strategy_analyst",
        output_type=StrategyAssessment,
        instructions=(
            "Evaluate only the named, versioned strategy skill. State invalidation and failure "
            "modes; do not invent executable strategy rules."
        ),
    )
    microstructure_agent = Agent(
        specialist_model,
        name="microstructure_analyst",
        output_type=MicrostructureAssessment,
        instructions=(
            "Assess spread, depth, turnover, funding, open interest, liquidation and execution "
            "quality using only supplied observations."
        ),
    )
    bull_agent = Agent(
        specialist_model,
        name="bull_researcher",
        output_type=BullCase,
        instructions="Build the strongest evidence-bounded supporting case and its uncertainties.",
    )
    bear_agent = Agent(
        specialist_model,
        name="bear_researcher",
        output_type=BearCase,
        instructions=(
            "Challenge the candidate, identify contrary evidence and concrete thesis breakers."
        ),
    )
    portfolio_advisor = Agent(
        specialist_model,
        name="personal_portfolio_advisor",
        deps_type=PortfolioAdvisorDeps,
        output_type=PortfolioAdvice,
        instructions=(
            "You are SignalOS's user-specific Personal Portfolio Advisor. Receive only one "
            "user's profile, learned preferences, current positions, and one global market "
            "decision. Your advice is read-only and untrusted until deterministic sizing and "
            "portfolio gates pass. Explicit profile settings outrank learned preferences. "
            "Behavior may only reduce risk or priority. Return no broker action."
        ),
        retries=2,
    )

    @portfolio_advisor.instructions
    def portfolio_context(ctx: RunContext[PortfolioAdvisorDeps]) -> str:
        return (
            f"Profile: {ctx.deps.profile.model_dump_json()}\n"
            f"Account equity: {ctx.deps.account_equity}; available: "
            f"{ctx.deps.available_balance}\n"
            f"Positions: {[position.model_dump(mode='json') for position in ctx.deps.positions]}\n"
            f"Learned preferences: "
            f"{[item.model_dump(mode='json') for item in ctx.deps.learned_preferences]}\n"
            f"Global decision: {ctx.deps.decision.model_dump_json()}\n"
            f"Deterministic signal: {ctx.deps.signal.model_dump_json()}"
        )

    director = Agent(
        director_model,
        name="investment_director",
        deps_type=DirectorDeps,
        output_type=InvestmentDecision,
        instructions=(
            "You are the SignalOS Investment Director. You coordinate read-only specialist "
            "analysis and never authorize, submit, modify, or cancel an order. Broker credentials "
            "and broker-write tools do not exist in your context. Model output is untrusted until "
            "deterministic quant, evidence, portfolio-risk, personalization, and human-approval "
            "gates pass. Requested leverage is advisory and may only be reduced by application "
            "policy."
        ),
        retries=2,
    )

    def prompt(ctx: RunContext[DirectorDeps], role: str) -> str:
        return (
            f"Role: {role}\nCandidate: {ctx.deps.candidate.model_dump_json()}\n"
            f"Strategy skill: {ctx.deps.strategy_skill_id}\n"
            f"Evidence summary: {ctx.deps.evidence_summary}\n"
            f"Due session windows: "
            f"{[sweep.model_dump(mode='json') for sweep in ctx.deps.session_sweeps]}\n"
            f"Deterministic signal: "
            f"{ctx.deps.signal.model_dump_json() if ctx.deps.signal is not None else 'none'}"
        )

    @director.tool
    async def delegate_session_analysis(ctx: RunContext[DirectorDeps]) -> SessionAssessment:
        """Delegate session-window analysis to the isolated Session Analyst."""

        return (await session_agent.run(prompt(ctx, "session"), usage=ctx.usage)).output

    @director.tool
    async def delegate_regime_analysis(ctx: RunContext[DirectorDeps]) -> RegimeAssessment:
        """Delegate deterministic-feature regime interpretation to the Regime Analyst."""

        return (await regime_agent.run(prompt(ctx, "regime"), usage=ctx.usage)).output

    @director.tool
    async def delegate_strategy_analysis(ctx: RunContext[DirectorDeps]) -> StrategyAssessment:
        """Delegate versioned strategy-skill analysis to the Strategy Analyst."""

        return (await strategy_agent.run(prompt(ctx, "strategy"), usage=ctx.usage)).output

    @director.tool
    async def delegate_microstructure_analysis(
        ctx: RunContext[DirectorDeps],
    ) -> MicrostructureAssessment:
        """Delegate spread, funding and execution-quality analysis."""

        return (
            await microstructure_agent.run(prompt(ctx, "microstructure"), usage=ctx.usage)
        ).output

    @director.tool
    async def delegate_bull_case(ctx: RunContext[DirectorDeps]) -> BullCase:
        """Delegate an independent evidence-bounded supporting case."""

        return (await bull_agent.run(prompt(ctx, "bull case"), usage=ctx.usage)).output

    @director.tool
    async def delegate_bear_case(ctx: RunContext[DirectorDeps]) -> BearCase:
        """Delegate an independent opposing case and thesis breakers."""

        return (await bear_agent.run(prompt(ctx, "bear case"), usage=ctx.usage)).output

    return InvestmentAgentSet(director=director, portfolio_advisor=portfolio_advisor)


def build_live_investment_agents(settings: Settings) -> InvestmentAgentSet | None:
    """Build the market-analysis family only when a real model credential exists."""

    if settings.openrouter_api_key is None or not settings.openrouter_api_key.get_secret_value():
        return None
    from signalos_backend.intelligence.agents import openrouter_model

    return build_investment_agents(
        director_model=openrouter_model(settings, settings.producer_model),
        specialist_model=openrouter_model(settings, settings.verifier_model),
    )
