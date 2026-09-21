from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from signalos_backend.brokers.domain import AccountEquityRange
from signalos_backend.domain import utc_now


class DrawdownStatus(StrEnum):
    NORMAL = "normal"
    WARNING = "warning"
    BREACHED = "breached"
    STALE = "stale"


class PortfolioRiskState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    connection_id: UUID
    status: DrawdownStatus
    high_water_equity: Decimal = Field(ge=0)
    current_equity: Decimal = Field(ge=0)
    drawdown_pct: Decimal = Field(ge=0, le=1)
    limit_pct: Decimal = Field(gt=0, le=1)
    new_risk_allowed: bool
    observed_at: datetime
    evaluated_at: datetime


class DrawdownLimitBreached(ValueError):
    """New exposure is blocked by the portfolio risk state."""


class RiskUsers(Protocol):
    async def get_profile(self, user_id: str): ...


class RiskBrokers(Protocol):
    async def get_account_equity_range(self, *, user_id: str) -> AccountEquityRange | None: ...


class NewRiskGate(Protocol):
    async def require_new_risk_allowed(self, *, user_id: str) -> PortfolioRiskState: ...


class PortfolioRiskService:
    def __init__(
        self,
        *,
        users: RiskUsers,
        brokers: RiskBrokers,
        clock: Callable[[], datetime] = utc_now,
        max_snapshot_age: timedelta = timedelta(minutes=5),
        warning_ratio: Decimal = Decimal("0.75"),
    ) -> None:
        self.users = users
        self.brokers = brokers
        self.clock = clock
        self.max_snapshot_age = max_snapshot_age
        self.warning_ratio = warning_ratio

    async def state(self, *, user_id: str) -> PortfolioRiskState:
        profile = await self.users.get_profile(user_id)
        equity = await self.brokers.get_account_equity_range(user_id=user_id)
        if profile is None or equity is None:
            raise DrawdownLimitBreached("current portfolio risk state is unavailable")

        now = self.clock().astimezone(UTC)
        observed_at = equity.observed_at.astimezone(UTC)
        limit = profile.adaptive_mandate.max_portfolio_drawdown_pct
        drawdown = (
            max(
                (equity.high_water_equity - equity.current_equity)
                / equity.high_water_equity,
                Decimal("0"),
            )
            if equity.high_water_equity > 0
            else Decimal("0")
        )
        if now - observed_at > self.max_snapshot_age:
            status = DrawdownStatus.STALE
        elif drawdown >= limit:
            status = DrawdownStatus.BREACHED
        elif drawdown >= limit * self.warning_ratio:
            status = DrawdownStatus.WARNING
        else:
            status = DrawdownStatus.NORMAL
        return PortfolioRiskState(
            connection_id=equity.connection_id,
            status=status,
            high_water_equity=equity.high_water_equity,
            current_equity=equity.current_equity,
            drawdown_pct=drawdown,
            limit_pct=limit,
            new_risk_allowed=status in {DrawdownStatus.NORMAL, DrawdownStatus.WARNING},
            observed_at=observed_at,
            evaluated_at=now,
        )

    async def require_new_risk_allowed(self, *, user_id: str) -> PortfolioRiskState:
        state = await self.state(user_id=user_id)
        if not state.new_risk_allowed:
            if state.status is DrawdownStatus.STALE:
                raise DrawdownLimitBreached("portfolio equity is stale; synchronize the account")
            raise DrawdownLimitBreached("portfolio drawdown limit reached; new risk is paused")
        return state
