from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext, UsageLimits

from signalos_backend.config import Settings
from signalos_backend.users.domain import (
    ExperienceLevel,
    InvestmentGoal,
    InvestmentProfile,
    PersonalizedMarket,
    PersonalizedPreferences,
    PersonalizedSession,
    PersonalizedStrategyFamily,
)


@dataclass(frozen=True)
class GeneratedPersonalization:
    preferences: PersonalizedPreferences
    source: str


@dataclass(frozen=True)
class PersonalizationGenerator:
    """Turns explicit onboarding facts into editable preferences, never hard limits."""

    agent: Agent[InvestmentProfile, PersonalizedPreferences] | None = None

    async def generate(self, profile: InvestmentProfile) -> GeneratedPersonalization:
        if self.agent is not None:
            try:
                result = await asyncio.wait_for(
                    self.agent.run(
                        (
                            "Create a concise, personalized investment preference policy from the "
                            "supplied onboarding profile. Infer what to prioritize and avoid, "
                            "but do "
                            "not create or alter leverage, loss, drawdown, position-size, "
                            "asset-access, or execution limits. The deterministic safety mandate "
                            "remains authoritative."
                        ),
                        deps=profile,
                        usage_limits=UsageLimits(
                            request_limit=2,
                            tool_calls_limit=0,
                            output_tokens_limit=1_200,
                        ),
                    ),
                    timeout=8,
                )
                return GeneratedPersonalization(result.output, "ai_generated")
            except Exception:
                # Personalization must never block onboarding because a model provider is down.
                # The fallback is deterministic, typed, and visibly identified in the API.
                pass
        return GeneratedPersonalization(
            deterministic_personalization(profile),
            "deterministic_fallback",
        )


def build_personalization_generator(settings: Settings) -> PersonalizationGenerator:
    if settings.openrouter_api_key is None or not settings.openrouter_api_key.get_secret_value():
        return PersonalizationGenerator()

    from signalos_backend.intelligence.agents import openrouter_model

    agent = Agent(
        openrouter_model(settings, settings.producer_model),
        name="user_personalization_advisor",
        deps_type=InvestmentProfile,
        output_type=PersonalizedPreferences,
        instructions=(
            "You are SignalOS's User Personalization Advisor. Convert explicit onboarding facts "
            "into an editable preference policy used to rank and explain opportunities. Never "
            "invent financial facts, promise returns, or set hard risk limits. The supplied "
            "deterministic mandate is read-only and always outranks your preferences."
        ),
        retries=2,
    )

    @agent.instructions
    def profile_context(ctx: RunContext[InvestmentProfile]) -> str:
        return f"Onboarding profile and safety mandate: {ctx.deps.model_dump_json()}"

    return PersonalizationGenerator(agent)


def deterministic_personalization(profile: InvestmentProfile) -> PersonalizedPreferences:
    """Safe, reproducible policy used when the configured model is unavailable."""

    goals = set(profile.goals)
    markets = [PersonalizedMarket.SPOT]
    if profile.adaptive_mandate.derivatives_eligible:
        markets.append(PersonalizedMarket.PERPETUALS)

    strategies: list[PersonalizedStrategyFamily] = []
    if InvestmentGoal.CAPITAL_GROWTH in goals:
        strategies.extend(
            (
                PersonalizedStrategyFamily.TREND,
                PersonalizedStrategyFamily.MOMENTUM,
                PersonalizedStrategyFamily.BREAKOUT,
            )
        )
    if InvestmentGoal.CAPITAL_PRESERVATION in goals:
        strategies.extend(
            (
                PersonalizedStrategyFamily.MEAN_REVERSION,
                PersonalizedStrategyFamily.VOLATILITY,
            )
        )
    if InvestmentGoal.INCOME in goals and profile.adaptive_mandate.derivatives_eligible:
        strategies.append(PersonalizedStrategyFamily.FUNDING_CARRY)
    if not strategies:
        strategies.extend(
            (
                PersonalizedStrategyFamily.TREND,
                PersonalizedStrategyFamily.MEAN_REVERSION,
            )
        )

    sessions: tuple[PersonalizedSession, ...] = ()
    if profile.trading_experience in {ExperienceLevel.INTERMEDIATE, ExperienceLevel.ADVANCED}:
        sessions = (PersonalizedSession.LONDON, PersonalizedSession.NEW_YORK)

    objectives = tuple(goal.value.replace("_", " ") for goal in profile.goals)
    posture = profile.adaptive_mandate.risk_posture.replace("_", " ")
    avoid = ["stale market data", "illiquid markets", "unapproved strategy versions"]
    if not profile.adaptive_mandate.derivatives_eligible:
        avoid.append("derivatives exposure")

    return PersonalizedPreferences(
        investor_summary=(
            f"A {posture} investor focused on {', '.join(objectives)} with "
            f"{profile.time_horizon.value.replace('_', ' ')} decision horizons."
        ),
        priority_objectives=objectives,
        preferred_markets=tuple(markets),
        preferred_strategy_families=tuple(dict.fromkeys(strategies))[:5],
        preferred_sessions=sessions,
        holding_periods=profile.holding_periods,
        explanation_detail=profile.explanation_detail,
        notification_frequency=profile.notification_frequency,
        avoid_conditions=tuple(avoid),
        rationale=(
            "Derived from explicit onboarding answers.",
            "Editable preferences remain below deterministic safety ceilings.",
        ),
    )
