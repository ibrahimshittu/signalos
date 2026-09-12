from datetime import UTC, datetime

from signalos_backend.users.domain import InvestmentProfile, InvestmentProfileInput
from signalos_backend.users.mandate import derive_adaptive_mandate
from signalos_backend.users.personalization import deterministic_personalization


def profile(**overrides) -> InvestmentProfile:
    payload = InvestmentProfileInput(
        goals=("capital_growth", "income"),
        time_horizon="swing",
        liquidity_need="low",
        investing_experience="advanced",
        trading_experience="advanced",
        products_traded=("crypto_spot", "futures"),
        decision_frequency="daily",
        drawdown_response="hold",
        holding_periods=("multi_day", "multi_week"),
        explanation_detail="standard",
        notification_frequency="opportunities_only",
        disclosures_accepted=True,
        **overrides,
    )
    now = datetime(2026, 8, 15, tzinfo=UTC)
    return InvestmentProfile(
        user_id="user-a",
        **payload.model_dump(),
        disclosures_accepted_at=now,
        created_at=now,
        updated_at=now,
        adaptive_mandate=derive_adaptive_mandate(payload),
    )


def test_personalization_uses_all_profile_facts_without_creating_risk_limits():
    user = profile()

    policy = deterministic_personalization(user)

    assert user.adaptive_mandate.max_leverage == 20
    assert policy.preferred_markets == ("spot", "linear")
    assert "funding_carry" in policy.preferred_strategy_families
    assert policy.preferred_sessions == ("london", "new_york")
    assert policy.holding_periods == user.holding_periods
    assert not hasattr(policy, "max_leverage")
