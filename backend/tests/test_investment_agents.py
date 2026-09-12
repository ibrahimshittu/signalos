from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic_ai.models.test import TestModel

from signalos_backend.investment.agents import (
    DirectorDeps,
    PortfolioAdvisorDeps,
    build_investment_agents,
)
from signalos_backend.investment.domain import (
    DecisionAction,
    InvestmentDecision,
    PortfolioAdvice,
    PortfolioProfileContext,
)
from signalos_backend.investment.gates import GateInput, MandatoryGateEvaluator
from signalos_backend.market.domain import MarketCandidate, MarketCategory
from signalos_backend.market.signals import StrategySignal
from signalos_backend.proposals.domain import OrderSide


def candidate() -> MarketCandidate:
    return MarketCandidate(
        category=MarketCategory.LINEAR,
        symbol="ETHUSDT",
        activity_score=Decimal("0.91"),
        turnover_24h=Decimal("800000000"),
        price_change_24h=Decimal("0.04"),
        spread_bps=Decimal("1.2"),
        observed_at=datetime(2026, 8, 14, 12, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_director_exposes_only_typed_read_only_specialist_delegations():
    director_model = TestModel(call_tools="all")
    specialist_model = TestModel(call_tools=[])
    agents = build_investment_agents(
        director_model=director_model,
        specialist_model=specialist_model,
    )

    result = await agents.director.run(
        "Assess this deterministic market candidate.",
        deps=DirectorDeps(
            candidate=candidate(),
            strategy_skill_id="session-opening-breakout",
            evidence_summary="Replicated on an immutable dataset.",
        ),
    )

    assert isinstance(result.output, InvestmentDecision)
    assert Decimal("0") <= result.output.confidence <= Decimal("1")
    assert Decimal("1") <= result.output.requested_leverage <= Decimal("20")
    tools = {tool.name for tool in director_model.last_model_request_parameters.function_tools}
    assert tools == {
        "delegate_session_analysis",
        "delegate_regime_analysis",
        "delegate_strategy_analysis",
        "delegate_microstructure_analysis",
        "delegate_bull_case",
        "delegate_bear_case",
    }
    assert not any("order" in name or "broker" in name or "trade" in name for name in tools)


@pytest.mark.asyncio
async def test_personal_portfolio_advisor_receives_typed_identifier_free_context():
    model = TestModel(call_tools=[])
    agents = build_investment_agents(director_model=model, specialist_model=model)
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    advice = await agents.advise(
        PortfolioAdvisorDeps(
            profile=PortfolioProfileContext(
                goals=("capital_growth",),
                time_horizon="swing",
                liquidity_need="low",
                investing_experience="advanced",
                trading_experience="advanced",
                products_traded=("crypto_spot", "futures"),
                decision_frequency="weekly",
                drawdown_response="hold",
                holding_periods=("multi_day",),
                explanation_detail="detailed",
                risk_posture="selective_growth",
                max_loss_per_trade_pct=Decimal("0.01"),
                max_leverage=Decimal("20"),
                derivatives_eligible=True,
            ),
            account_equity=Decimal("10000"),
            available_balance=Decimal("7000"),
            positions=(),
            learned_preferences=(),
            decision=InvestmentDecision(
                candidate_symbol="BTCUSDT",
                action=DecisionAction.PROPOSE,
                thesis="A replicated continuation signal is active on completed candles.",
                opposing_case="The continuation can fail if the regime changes abruptly.",
                confidence=Decimal("0.75"),
                requested_leverage=Decimal("5"),
            ),
            signal=StrategySignal(
                strategy_id="managed-trend-filter",
                strategy_version="1.0.0",
                category=MarketCategory.LINEAR,
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                entry_price=Decimal("68000"),
                stop_loss=Decimal("67000"),
                take_profit=Decimal("70000"),
                suggested_leverage=Decimal("5"),
                reward_to_risk=Decimal("2"),
                trend_strength=Decimal("0.02"),
                realized_volatility=Decimal("0.03"),
                volume_ratio=Decimal("1.2"),
                market_observed_at=now,
            ),
        )
    )

    assert isinstance(advice, PortfolioAdvice)
    assert model.last_model_request_parameters.function_tools == []


def test_mandatory_gates_reject_stale_or_unapproved_candidates():
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    report = MandatoryGateEvaluator().evaluate(
        GateInput(
            strategy_status="validated",
            backtest_passed=True,
            evidence_replicated=False,
            portfolio_risk_passed=True,
            market_observed_at=now - timedelta(minutes=5),
            evaluated_at=now,
        )
    )

    assert report.passed is False
    assert report.failures == (
        "strategy_not_approved",
        "evidence_not_replicated",
        "market_data_stale",
    )


def test_mandatory_gates_pass_only_when_every_application_check_passes():
    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    report = MandatoryGateEvaluator().evaluate(
        GateInput(
            strategy_status="approved",
            backtest_passed=True,
            evidence_replicated=True,
            portfolio_risk_passed=True,
            market_observed_at=now - timedelta(seconds=30),
            evaluated_at=now,
        )
    )

    assert report.passed is True
    assert report.failures == ()
