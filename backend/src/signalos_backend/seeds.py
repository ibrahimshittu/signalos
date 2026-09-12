from __future__ import annotations

from datetime import UTC, datetime

from signalos_backend.domain import (
    CostModel,
    EntryExitRules,
    FeatureSpec,
    RiskConstraints,
    SignalClause,
    SignalExpression,
    SkillManifest,
    SkillStatus,
    StrategyFamily,
    StrategySpec,
    StrategyStatus,
    ToolManifest,
    ValidationRequirements,
)
from signalos_backend.intelligence.registries import SkillRegistry, StrategyRegistry, ToolRegistry

SKILLS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "risk-management",
        "Apply risk constraints, vetoes, drawdown controls, and behavioural safeguards.",
        ("risk", "drawdown", "safety"),
    ),
    (
        "backtest-validation",
        "Detect leakage and validate backtests, costs, robustness, and calibration.",
        ("backtest", "validation", "sharpe"),
    ),
    (
        "portfolio-construction",
        "Assess allocation, diversification, correlation, concentration, and reserves.",
        ("portfolio", "allocation", "diversification"),
    ),
    (
        "market-regimes",
        "Classify volatility, trend, liquidity, and cross-asset market regimes.",
        ("regime", "volatility", "cycle"),
    ),
    (
        "momentum-trend",
        "Evaluate momentum and trend-following hypotheses across declared horizons.",
        ("momentum", "trend"),
    ),
    (
        "mean-reversion",
        "Evaluate mean-reversion and statistical-relationship hypotheses carefully.",
        ("mean reversion", "zscore", "spread"),
    ),
    (
        "funding-and-basis",
        "Analyze funding, futures basis, carry, crowding, and liquidation risk.",
        ("funding", "basis", "carry"),
    ),
    (
        "microstructure",
        "Analyze spread, depth, order flow, liquidity, and market impact.",
        ("spread", "depth", "order book"),
    ),
    (
        "execution-quality",
        "Measure fill quality, fees, slippage, latency, and implementation shortfall.",
        ("execution", "slippage", "fees"),
    ),
    (
        "crypto-network-analysis",
        "Analyze protocol activity, token structure, custody, and network risks.",
        ("on-chain", "protocol", "token"),
    ),
    (
        "company-fundamentals",
        "Analyze filings, cash flow, balance sheets, valuation, and business quality.",
        ("company", "filing", "valuation"),
    ),
    (
        "macro-liquidity",
        "Analyze rates, inflation, currency, liquidity, and cross-asset transmission.",
        ("macro", "rates", "liquidity"),
    ),
    (
        "source-verification",
        "Verify primary evidence, freshness, independence, contradictions, and provenance.",
        ("source", "citation", "verify"),
    ),
    (
        "financial-explanation",
        "Explain financial evidence in plain language without hiding uncertainty.",
        ("explain", "why", "compare"),
    ),
)


def build_skill_registry() -> SkillRegistry:
    registry = SkillRegistry()
    now = datetime.now(UTC)
    for stable_id, description, triggers in SKILLS:
        manifest = SkillManifest(
            stable_id=stable_id,
            version="1.0.0",
            description=description,
            routing_triggers=triggers,
            instructions=(
                f"Use the {stable_id} discipline only when routed. Separate verified evidence from "
                "interpretation, state failure modes, and never bypass deterministic policy."
            ),
            reviewer="SignalOS Intelligence Governance",
            effective_at=now,
            evaluation_suite=f"evals/{stable_id}.yaml",
            status=SkillStatus.QUARANTINED,
        )
        registry.register_candidate(manifest)
        registry.promote(stable_id, "1.0.0", operator_approved=True)
    return registry


def build_tool_registry() -> ToolRegistry:
    analyst_agents = (
        "research-planner",
        "source-investigator",
        "quantitative-analyst",
        "fundamental-analyst",
        "crypto-analyst",
        "macro-analyst",
        "strategy-researcher",
        "risk-skeptic",
        "evidence-verifier",
        "ask-signalos-analyst",
    )
    definitions = (
        ("market.ohlcv", "Retrieve timestamped market OHLCV observations.", True),
        (
            "market.microstructure",
            "Retrieve spread, depth, funding, basis, and open interest.",
            True,
        ),
        ("filings.sec", "Retrieve regulator-hosted filings and company fundamentals.", True),
        ("macro.fred", "Retrieve official FRED macroeconomic series and release metadata.", True),
        ("crypto.network", "Retrieve approved protocol and network activity metrics.", True),
        (
            "news.discovery",
            "Discover news from approved providers for quarantine and verification.",
            False,
        ),
        ("evidence.search", "Search admitted claims and their source provenance.", True),
        ("portfolio.history", "Read account portfolio state and historical decisions.", False),
        (
            "experiment.submit",
            "Submit a typed experiment to the deterministic isolated runner.",
            False,
        ),
        (
            "finance.calculate",
            "Perform deterministic financial calculations and comparisons.",
            True,
        ),
    )
    return ToolRegistry(
        ToolManifest(
            stable_id=stable_id,
            purpose=purpose,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            access="read",
            required_role="research",
            allowed_agents=analyst_agents,
            data_sensitivity="public",
            freshness_seconds=900,
            cache_ttl_seconds=60,
            code_mode=code_mode,
        )
        for stable_id, purpose, code_mode in definitions
    )


def build_strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    momentum = FeatureSpec(name="moving_average", window=50)
    entry = SignalExpression(
        clauses=(SignalClause(feature="moving_average", operator="gt", value="price"),)
    )
    exit_rule = SignalExpression(
        clauses=(SignalClause(feature="moving_average", operator="lt", value="price"),)
    )
    spec = StrategySpec(
        id="managed-trend-filter",
        version="1.0.0",
        family=StrategyFamily.MOMENTUM_TREND,
        status=StrategyStatus.QUARANTINED,
        thesis=(
            "A slow trend filter may reduce prolonged drawdown while preserving strategic exposure."
        ),
        eligible_universe=("BTC", "ETH", "SOL", "USDC"),
        holding_horizon="weekly",
        required_data=("adjusted_ohlcv",),
        features=(momentum,),
        signal_expression=entry,
        entry_and_exit_rules=EntryExitRules(entry=entry, exit=exit_rule, cooldown_bars=7),
        portfolio_role=(
            "A shadow-only drawdown-aware tilt around the approved strategic allocation."
        ),
        risk_constraints=RiskConstraints(),
        cost_model=CostModel(),
        evidence_references=(),
        known_failure_modes=(
            "Whipsaw in range-bound markets",
            "Delayed re-entry after rapid reversals",
        ),
        validation_requirements=ValidationRequirements(),
    )
    registry.register_candidate(spec)
    return registry
