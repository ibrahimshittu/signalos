from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from signalos_backend.users.domain import InvestmentProfileInput
from signalos_backend.users.mandate import derive_adaptive_mandate


def profile_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "goals": ["capital_growth"],
        "intended_capital": "10000",
        "time_horizon": "swing",
        "liquidity_need": "moderate",
        "investing_experience": "intermediate",
        "trading_experience": "beginner",
        "products_traded": ["stocks_etfs", "crypto_spot"],
        "decision_frequency": "monthly",
        "drawdown_response": "hold",
        "holding_periods": ["multi_day"],
        "explanation_detail": "detailed",
        "notification_frequency": "opportunities_only",
        "disclosures_accepted": True,
    }
    payload.update(overrides)
    return payload


def test_profile_rejects_user_authored_trade_risk_settings() -> None:
    with pytest.raises(ValidationError, match="max_loss_per_trade_pct"):
        InvestmentProfileInput.model_validate(
            profile_payload(
                max_loss_per_trade_pct="0.02",
                max_leverage="5",
            )
        )


def test_newer_investor_gets_a_capital_protective_mandate() -> None:
    profile = InvestmentProfileInput.model_validate(
        profile_payload(
            investing_experience="none",
            trading_experience="none",
            products_traded=["stocks_etfs"],
            decision_frequency="first_time",
            drawdown_response="unsure",
        )
    )

    mandate = derive_adaptive_mandate(profile)

    assert mandate.risk_posture == "capital_protective"
    assert mandate.max_loss_per_trade_pct == Decimal("0.005")
    assert mandate.max_leverage == Decimal("1")
    assert mandate.derivatives_eligible is False


def test_experienced_derivatives_user_gets_a_bounded_growth_mandate() -> None:
    profile = InvestmentProfileInput.model_validate(
        profile_payload(
            liquidity_need="low",
            investing_experience="advanced",
            trading_experience="advanced",
            products_traded=["stocks_etfs", "crypto_spot", "futures"],
            decision_frequency="weekly",
            drawdown_response="hold",
        )
    )

    mandate = derive_adaptive_mandate(profile)

    assert mandate.risk_posture == "selective_growth"
    assert mandate.max_loss_per_trade_pct == Decimal("0.01")
    assert mandate.max_leverage == Decimal("20")
    assert mandate.derivatives_eligible is True


def test_capital_preservation_overrides_advanced_trading_experience() -> None:
    profile = InvestmentProfileInput.model_validate(
        profile_payload(
            goals=["capital_preservation"],
            investing_experience="advanced",
            trading_experience="advanced",
            products_traded=["stocks_etfs", "futures"],
            decision_frequency="daily",
        )
    )

    mandate = derive_adaptive_mandate(profile)

    assert mandate.risk_posture == "capital_protective"
    assert mandate.max_leverage == Decimal("1")
    assert "capital_preservation_goal" in mandate.reasons
