from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from signalos_backend.domain import RiskTier


class AllocationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account_id: str
    risk_tier: RiskTier
    current: dict[str, Decimal]
    proposed: dict[str, Decimal]
    data_as_of: datetime
    last_rebalance_at: datetime | None = None
    paused: bool = False
    kill_switch: bool = False
    source_disagreement: bool = False

    @model_validator(mode="after")
    def allocations_sum_to_one(self) -> AllocationProposal:
        for label, allocation in (("current", self.current), ("proposed", self.proposed)):
            if abs(sum(allocation.values(), Decimal("0")) - Decimal("1")) > Decimal("0.0001"):
                raise ValueError(f"{label} allocations must sum to 1")
        return self


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    allowed: bool
    turnover: Decimal
    reasons: tuple[str, ...]
    policy_version: str = "portfolio-policy-1.0.0"


_TILT_LIMITS = {
    RiskTier.CAUTIOUS: {"BTC": Decimal("0.04"), "ETH": Decimal("0.04"), "SOL": Decimal("0.02")},
    RiskTier.BALANCED: {"BTC": Decimal("0.05"), "ETH": Decimal("0.05"), "SOL": Decimal("0.03")},
    RiskTier.ADVENTUROUS: {
        "BTC": Decimal("0.07"),
        "ETH": Decimal("0.07"),
        "SOL": Decimal("0.05"),
    },
}
_RESERVE_FLOORS = {
    RiskTier.CAUTIOUS: Decimal("0.35"),
    RiskTier.BALANCED: Decimal("0.10"),
    RiskTier.ADVENTUROUS: Decimal("0.05"),
}
_MANAGED = {"BTC", "ETH", "SOL", "USDC"}


def evaluate_proposal(
    proposal: AllocationProposal, *, now: datetime | None = None
) -> PolicyDecision:
    now = now or datetime.now(UTC)
    reasons: list[str] = []
    if proposal.paused:
        reasons.append("account_paused")
    if proposal.kill_switch:
        reasons.append("global_kill_switch")
    if proposal.source_disagreement:
        reasons.append("source_disagreement")
    if set(proposal.proposed) != _MANAGED or set(proposal.current) != _MANAGED:
        reasons.append("managed_universe_violation")
    if now - proposal.data_as_of > timedelta(minutes=15):
        reasons.append("stale_data")
    if proposal.last_rebalance_at and now - proposal.last_rebalance_at < timedelta(hours=24):
        reasons.append("rebalance_frequency_limit")
    turnover = sum(
        (
            abs(
                proposal.proposed.get(asset, Decimal("0"))
                - proposal.current.get(asset, Decimal("0"))
            )
            for asset in _MANAGED
        ),
        Decimal("0"),
    ) / Decimal("2")
    if turnover > Decimal("0.10"):
        reasons.append("turnover_limit")
    if proposal.proposed.get("USDC", Decimal("0")) < _RESERVE_FLOORS[proposal.risk_tier]:
        reasons.append("reserve_floor")
    limits = _TILT_LIMITS[proposal.risk_tier]
    for asset, limit in limits.items():
        if (
            abs(
                proposal.proposed.get(asset, Decimal("0"))
                - proposal.current.get(asset, Decimal("0"))
            )
            > limit
        ):
            reasons.append(f"tilt_limit:{asset}")
    return PolicyDecision(allowed=not reasons, turnover=turnover, reasons=tuple(reasons))
