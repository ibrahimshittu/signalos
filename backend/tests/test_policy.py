from datetime import UTC, datetime
from decimal import Decimal

from signalos_backend.domain import RiskTier
from signalos_backend.portfolio.policy import AllocationProposal, evaluate_proposal


def allocation(btc: str, eth: str, sol: str, usdc: str):
    return {
        key: Decimal(value)
        for key, value in {"BTC": btc, "ETH": eth, "SOL": sol, "USDC": usdc}.items()
    }


def test_bounded_balanced_tilt_is_allowed():
    proposal = AllocationProposal(
        account_id="a1",
        risk_tier=RiskTier.BALANCED,
        current=allocation("0.45", "0.30", "0.10", "0.15"),
        proposed=allocation("0.47", "0.29", "0.09", "0.15"),
        data_as_of=datetime.now(UTC),
    )
    assert evaluate_proposal(proposal).allowed is True


def test_reserve_turnover_and_kill_switch_are_hard_vetoes():
    proposal = AllocationProposal(
        account_id="a1",
        risk_tier=RiskTier.CAUTIOUS,
        current=allocation("0.30", "0.20", "0.10", "0.40"),
        proposed=allocation("0.60", "0.25", "0.10", "0.05"),
        data_as_of=datetime.now(UTC),
        kill_switch=True,
    )
    decision = evaluate_proposal(proposal)
    assert decision.allowed is False
    assert "global_kill_switch" in decision.reasons
    assert "reserve_floor" in decision.reasons
    assert "turnover_limit" in decision.reasons
