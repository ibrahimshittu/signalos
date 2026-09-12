from __future__ import annotations

from decimal import Decimal

from signalos_backend.users.domain import (
    AdaptiveRiskMandate,
    DecisionFrequency,
    DrawdownResponse,
    ExperienceLevel,
    InvestmentGoal,
    InvestmentProfileInput,
    LiquidityNeed,
    TradedProduct,
)

_DERIVATIVES = {TradedProduct.FUTURES, TradedProduct.OPTIONS}


def derive_adaptive_mandate(profile: InvestmentProfileInput) -> AdaptiveRiskMandate:
    """Derive hard proposal ceilings from suitability inputs and platform policy.

    The investment agents may recommend stops, targets, and requested leverage, but this
    deterministic policy is the final ceiling. It never learns a higher risk limit from behavior.
    """

    products = set(profile.products_traded)
    reasons: list[str] = []
    protective = False

    if InvestmentGoal.CAPITAL_PRESERVATION in profile.goals:
        protective = True
        reasons.append("capital_preservation_goal")
    if profile.liquidity_need is LiquidityNeed.HIGH:
        protective = True
        reasons.append("high_liquidity_need")
    if profile.investing_experience is ExperienceLevel.NONE:
        protective = True
        reasons.append("new_investor")
    if profile.trading_experience is ExperienceLevel.NONE:
        protective = True
        reasons.append("new_trader")
    if profile.drawdown_response in {DrawdownResponse.EXIT, DrawdownResponse.UNSURE}:
        protective = True
        reasons.append("drawdown_uncertainty")

    derivatives_experience = bool(products & _DERIVATIVES)
    derivatives_eligible = derivatives_experience and profile.trading_experience in {
        ExperienceLevel.INTERMEDIATE,
        ExperienceLevel.ADVANCED,
    }

    if protective:
        return AdaptiveRiskMandate(
            risk_posture="capital_protective",
            max_loss_per_trade_pct=Decimal("0.005"),
            max_portfolio_drawdown_pct=Decimal("0.06"),
            max_leverage=Decimal("1"),
            derivatives_eligible=False,
            reasons=tuple(reasons),
        )

    selective_growth = (
        InvestmentGoal.CAPITAL_GROWTH in profile.goals
        and profile.liquidity_need is LiquidityNeed.LOW
        and profile.investing_experience is ExperienceLevel.ADVANCED
        and profile.trading_experience is ExperienceLevel.ADVANCED
        and profile.decision_frequency in {DecisionFrequency.WEEKLY, DecisionFrequency.DAILY}
        and derivatives_eligible
    )
    if selective_growth:
        return AdaptiveRiskMandate(
            risk_posture="selective_growth",
            max_loss_per_trade_pct=Decimal("0.01"),
            max_portfolio_drawdown_pct=Decimal("0.12"),
            max_leverage=Decimal("20"),
            derivatives_eligible=True,
            reasons=("advanced_market_experience", "bounded_derivatives_experience"),
        )

    return AdaptiveRiskMandate(
        risk_posture="measured",
        max_loss_per_trade_pct=Decimal("0.0075"),
        max_portfolio_drawdown_pct=Decimal("0.08"),
        max_leverage=Decimal("1.5") if derivatives_eligible else Decimal("1"),
        derivatives_eligible=derivatives_eligible,
        reasons=(
            "balanced_suitability_inputs",
            "derivatives_experience_verified" if derivatives_eligible else "spot_first",
        ),
    )
