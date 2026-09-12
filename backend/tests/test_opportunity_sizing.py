from __future__ import annotations

from decimal import Decimal

import pytest

from signalos_backend.investment.sizing import (
    OpportunitySizingInput,
    OpportunitySizingPolicy,
    SizingRejected,
)
from signalos_backend.market.domain import MarketCategory
from signalos_backend.proposals.domain import OrderSide


def sizing_input(**overrides: object) -> OpportunitySizingInput:
    values: dict[str, object] = {
        "category": MarketCategory.LINEAR,
        "side": OrderSide.BUY,
        "entry_price": Decimal("100"),
        "stop_loss": Decimal("95"),
        "take_profit": Decimal("112"),
        "account_equity": Decimal("10000"),
        "available_balance": Decimal("4000"),
        "current_gross_exposure": Decimal("2500"),
        "correlated_exposure_pct": Decimal("0.25"),
        "max_loss_per_trade_pct": Decimal("0.01"),
        "mandate_max_leverage": Decimal("20"),
        "broker_max_leverage": Decimal("10"),
        "agent_requested_leverage": Decimal("15"),
        "agent_confidence": Decimal("0.80"),
        "quantity_step": Decimal("0.01"),
        "minimum_order_quantity": Decimal("0.01"),
        "minimum_notional": Decimal("5"),
        "round_trip_cost_bps": Decimal("20"),
    }
    values.update(overrides)
    return OpportunitySizingInput.model_validate(values)


def test_sizes_each_opportunity_from_stop_portfolio_and_broker_limits() -> None:
    sizing = OpportunitySizingPolicy().size(sizing_input())

    assert sizing.leverage == Decimal("10")
    assert sizing.quantity == Decimal("12.54")
    assert sizing.notional == Decimal("1254.00")
    assert sizing.required_margin == Decimal("125.40")
    assert sizing.estimated_max_loss == Decimal("65.208")
    assert sizing.risk_budget == Decimal("65.250000")
    assert sizing.reward_to_risk > Decimal("2")
    assert "broker_leverage_cap" in sizing.constraints


def test_correlated_exposure_can_only_reduce_the_risk_budget() -> None:
    uncorrelated = OpportunitySizingPolicy().size(
        sizing_input(correlated_exposure_pct=Decimal("0"))
    )
    correlated = OpportunitySizingPolicy().size(
        sizing_input(correlated_exposure_pct=Decimal("0.80"))
    )

    assert correlated.risk_budget < uncorrelated.risk_budget
    assert correlated.quantity < uncorrelated.quantity
    assert "correlation_budget_reduction" in correlated.constraints


def test_spot_opportunity_is_always_unleveraged() -> None:
    sizing = OpportunitySizingPolicy().size(
        sizing_input(
            category=MarketCategory.SPOT,
            mandate_max_leverage=Decimal("20"),
            broker_max_leverage=Decimal("100"),
            agent_requested_leverage=Decimal("20"),
        )
    )

    assert sizing.leverage == Decimal("1")
    assert "spot_unleveraged" in sizing.constraints


def test_rejects_an_opportunity_that_cannot_meet_exchange_minimums() -> None:
    with pytest.raises(SizingRejected, match="exchange minimum"):
        OpportunitySizingPolicy().size(
            sizing_input(
                account_equity=Decimal("10"),
                available_balance=Decimal("10"),
                current_gross_exposure=Decimal("0"),
                minimum_notional=Decimal("100"),
            )
        )


def test_rejects_invalid_directional_price_levels() -> None:
    with pytest.raises(ValueError, match="buy sizing requires"):
        sizing_input(stop_loss=Decimal("101"))
