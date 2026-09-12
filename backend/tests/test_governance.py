import pytest
from pydantic import ValidationError

from signalos_backend.domain import StrategyStatus, ToolManifest
from signalos_backend.seeds import build_strategy_registry


def test_strategy_cannot_skip_governance_states():
    registry = build_strategy_registry()
    with pytest.raises(ValueError, match="invalid transition"):
        registry.transition("managed-trend-filter", "1.0.0", StrategyStatus.APPROVED)


def test_strategy_approval_requires_operator():
    registry = build_strategy_registry()
    registry.transition("managed-trend-filter", "1.0.0", StrategyStatus.RESEARCH)
    registry.transition("managed-trend-filter", "1.0.0", StrategyStatus.VALIDATED)
    registry.transition("managed-trend-filter", "1.0.0", StrategyStatus.SHADOW)
    registry.transition("managed-trend-filter", "1.0.0", StrategyStatus.PROMOTION_PENDING)
    with pytest.raises(PermissionError):
        registry.transition("managed-trend-filter", "1.0.0", StrategyStatus.APPROVED)
    approved = registry.transition(
        "managed-trend-filter", "1.0.0", StrategyStatus.APPROVED, operator_approved=True
    )
    assert approved.status is StrategyStatus.APPROVED


def test_code_mode_rejects_mutation_and_sensitive_tools():
    base = dict(
        stable_id="portfolio.mutate",
        purpose="Attempt to mutate a portfolio from generated code.",
        input_schema={},
        output_schema={},
        required_role="research",
        allowed_agents=("quantitative-analyst",),
        freshness_seconds=1,
        code_mode=True,
    )
    with pytest.raises(ValidationError, match="read-only"):
        ToolManifest(**base, access="write")
    with pytest.raises(ValidationError, match="read-only"):
        ToolManifest(**base, data_sensitivity="account")
