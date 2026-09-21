from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from signalos_backend.brokers.domain import AccountEquityRange
from signalos_backend.investment.gates import MandatoryGateReport
from signalos_backend.portfolio.risk import (
    DrawdownLimitBreached,
    DrawdownStatus,
    PortfolioRiskService,
)
from signalos_backend.proposals.domain import CreateTradeProposal
from signalos_backend.proposals.service import ProposalService

NOW = datetime(2026, 9, 21, 12, tzinfo=UTC)


class Users:
    async def get_profile(self, user_id: str):
        assert user_id == "user-a"
        return SimpleNamespace(
            adaptive_mandate=SimpleNamespace(max_portfolio_drawdown_pct=Decimal("0.08"))
        )


class Brokers:
    def __init__(self, *, high: str, current: str, observed_at: datetime = NOW) -> None:
        self.range = AccountEquityRange(
            connection_id=uuid4(),
            high_water_equity=Decimal(high),
            current_equity=Decimal(current),
            observed_at=observed_at,
        )

    async def get_account_equity_range(self, *, user_id: str):
        assert user_id == "user-a"
        return self.range


async def test_drawdown_limit_blocks_new_risk() -> None:
    service = PortfolioRiskService(
        users=Users(),
        brokers=Brokers(high="10000", current="9200"),
        clock=lambda: NOW,
    )

    state = await service.state(user_id="user-a")

    assert state.status is DrawdownStatus.BREACHED
    assert state.drawdown_pct == Decimal("0.08")
    assert state.new_risk_allowed is False
    with pytest.raises(DrawdownLimitBreached, match="portfolio drawdown limit reached"):
        await service.require_new_risk_allowed(user_id="user-a")


async def test_drawdown_warns_before_limit_and_rejects_stale_equity() -> None:
    warning = await PortfolioRiskService(
        users=Users(),
        brokers=Brokers(high="10000", current="9400"),
        clock=lambda: NOW,
    ).state(user_id="user-a")
    stale = await PortfolioRiskService(
        users=Users(),
        brokers=Brokers(high="10000", current="9900", observed_at=NOW - timedelta(minutes=6)),
        clock=lambda: NOW,
        max_snapshot_age=timedelta(minutes=5),
    ).state(user_id="user-a")

    assert warning.status is DrawdownStatus.WARNING
    assert warning.new_risk_allowed is True
    assert stale.status is DrawdownStatus.STALE
    assert stale.new_risk_allowed is False


async def test_proposal_creation_stops_before_persistence_when_drawdown_is_breached() -> None:
    class BlockingRisk:
        async def require_new_risk_allowed(self, *, user_id: str):
            raise DrawdownLimitBreached("portfolio drawdown limit reached; new risk is paused")

    class ProfileUsers:
        async def get_profile(self, user_id: str):
            return SimpleNamespace(disclosures_accepted=True)

    service = ProposalService(
        users=ProfileUsers(),
        brokers=SimpleNamespace(),
        proposals=SimpleNamespace(),
        risk=BlockingRisk(),
    )

    with pytest.raises(DrawdownLimitBreached, match="new risk is paused"):
        await service.create(
            user_id="user-a",
            payload=CreateTradeProposal.model_construct(
                gate_report=MandatoryGateReport(passed=True, failures=())
            ),
        )
