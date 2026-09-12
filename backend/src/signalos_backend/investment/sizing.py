from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from signalos_backend.market.domain import MarketCategory
from signalos_backend.proposals.domain import OrderSide

PLATFORM_MAX_LEVERAGE = Decimal("20")


class OpportunitySizingInput(BaseModel):
    """Validated market, portfolio, policy, and exchange inputs for one opportunity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: MarketCategory
    side: OrderSide
    entry_price: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit: Decimal = Field(gt=0)
    account_equity: Decimal = Field(gt=0)
    available_balance: Decimal = Field(ge=0)
    current_gross_exposure: Decimal = Field(default=Decimal("0"), ge=0)
    correlated_exposure_pct: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    max_loss_per_trade_pct: Decimal = Field(gt=0, le=Decimal("0.02"))
    mandate_max_leverage: Decimal = Field(ge=1, le=PLATFORM_MAX_LEVERAGE)
    broker_max_leverage: Decimal = Field(ge=1, le=Decimal("200"))
    agent_requested_leverage: Decimal = Field(ge=1, le=PLATFORM_MAX_LEVERAGE)
    agent_confidence: Decimal = Field(ge=0, le=1)
    quantity_step: Decimal = Field(gt=0)
    minimum_order_quantity: Decimal = Field(ge=0)
    minimum_notional: Decimal = Field(ge=0)
    round_trip_cost_bps: Decimal = Field(default=Decimal("20"), ge=0, le=1_000)
    maximum_margin_utilization_pct: Decimal = Field(
        default=Decimal("0.35"), gt=0, le=Decimal("0.50")
    )
    minimum_reward_to_risk: Decimal = Field(default=Decimal("1.25"), gt=0, le=10)

    @model_validator(mode="after")
    def validate_directional_levels(self) -> OpportunitySizingInput:
        if self.side is OrderSide.BUY and not (
            self.stop_loss < self.entry_price < self.take_profit
        ):
            raise ValueError("buy sizing requires stop_loss < entry_price < take_profit")
        if self.side is OrderSide.SELL and not (
            self.take_profit < self.entry_price < self.stop_loss
        ):
            raise ValueError("sell sizing requires take_profit < entry_price < stop_loss")
        return self


class OpportunitySizing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    leverage: Decimal = Field(ge=1, le=PLATFORM_MAX_LEVERAGE)
    quantity: Decimal = Field(gt=0)
    notional: Decimal = Field(gt=0)
    required_margin: Decimal = Field(gt=0)
    risk_budget: Decimal = Field(gt=0)
    estimated_max_loss: Decimal = Field(gt=0)
    estimated_cost: Decimal = Field(ge=0)
    reward_to_risk: Decimal = Field(gt=0)
    constraints: tuple[str, ...]


class SizingRejected(ValueError):
    """The opportunity cannot produce a valid order inside deterministic boundaries."""


class OpportunitySizingPolicy:
    """Size an opportunity without allowing model output to loosen risk policy."""

    def size(self, input_: OpportunitySizingInput) -> OpportunitySizing:
        constraints: list[str] = []
        leverage = self._leverage(input_, constraints)

        risk_capital = input_.account_equity
        confidence_multiplier = Decimal("0.35") + Decimal("0.65") * input_.agent_confidence
        correlation_multiplier = max(Decimal("0.20"), Decimal("1") - input_.correlated_exposure_pct)
        if input_.correlated_exposure_pct > 0:
            constraints.append("correlation_budget_reduction")
        risk_budget = (
            risk_capital
            * input_.max_loss_per_trade_pct
            * confidence_multiplier
            * correlation_multiplier
        )

        stop_distance = abs(input_.entry_price - input_.stop_loss)
        target_distance = abs(input_.take_profit - input_.entry_price)
        cost_per_unit = input_.entry_price * input_.round_trip_cost_bps / Decimal("10000")
        loss_per_unit = stop_distance + cost_per_unit
        reward_per_unit = max(target_distance - cost_per_unit, Decimal("0"))
        reward_to_risk = reward_per_unit / loss_per_unit
        if reward_to_risk < input_.minimum_reward_to_risk:
            raise SizingRejected("opportunity reward-to-risk is below platform policy")

        quantity_by_risk = risk_budget / loss_per_unit
        exposure_ratio = min(
            input_.current_gross_exposure / input_.account_equity,
            Decimal("0.75"),
        )
        if exposure_ratio > 0:
            constraints.append("portfolio_exposure_margin_reduction")
        margin_budget = (
            input_.available_balance
            * input_.maximum_margin_utilization_pct
            * (Decimal("1") - exposure_ratio)
        )
        quantity_by_margin = margin_budget * leverage / input_.entry_price
        quantity = self._floor_to_step(
            min(quantity_by_risk, quantity_by_margin), input_.quantity_step
        )
        if quantity <= 0:
            raise SizingRejected("available risk and margin budgets cannot fund an order")

        notional = quantity * input_.entry_price
        if quantity < input_.minimum_order_quantity or notional < input_.minimum_notional:
            raise SizingRejected("sized order is below the exchange minimum")

        estimated_cost = quantity * cost_per_unit
        estimated_max_loss = quantity * loss_per_unit
        required_margin = notional / leverage
        if estimated_max_loss > risk_budget or required_margin > margin_budget:
            raise SizingRejected("rounded order exceeds deterministic risk or margin budget")

        return OpportunitySizing(
            leverage=leverage,
            quantity=quantity,
            notional=notional,
            required_margin=required_margin,
            risk_budget=risk_budget,
            estimated_max_loss=estimated_max_loss,
            estimated_cost=estimated_cost,
            reward_to_risk=reward_to_risk,
            constraints=tuple(dict.fromkeys(constraints)),
        )

    @staticmethod
    def _leverage(input_: OpportunitySizingInput, constraints: list[str]) -> Decimal:
        if input_.category is MarketCategory.SPOT:
            constraints.append("spot_unleveraged")
            return Decimal("1")
        leverage = min(
            input_.agent_requested_leverage,
            input_.mandate_max_leverage,
            input_.broker_max_leverage,
            PLATFORM_MAX_LEVERAGE,
        )
        if leverage < input_.agent_requested_leverage:
            if input_.mandate_max_leverage == leverage:
                constraints.append("adaptive_mandate_leverage_cap")
            if input_.broker_max_leverage == leverage:
                constraints.append("broker_leverage_cap")
            if leverage == PLATFORM_MAX_LEVERAGE:
                constraints.append("platform_leverage_cap")
        return leverage

    @staticmethod
    def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
        return (value / step).to_integral_value(rounding=ROUND_DOWN) * step
