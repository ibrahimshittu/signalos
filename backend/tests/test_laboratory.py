from signalos_backend.intelligence.laboratory import DeterministicExperimentRunner, ExperimentSpec
from signalos_backend.seeds import build_strategy_registry


def test_experiment_is_reproducible_and_cost_aware():
    strategy = build_strategy_registry().get("managed-trend-filter")
    prices = tuple(100 + ((index % 20) - 10) * 0.7 + index * 0.08 for index in range(600))
    spec = ExperimentSpec(
        strategy_id=strategy.id,
        strategy_version=strategy.version,
        prices=prices,
    )
    runner = DeterministicExperimentRunner()
    first = runner.run(strategy, spec)
    second = runner.run(strategy, spec)
    assert first.reproducibility_hash == second.reproducibility_hash
    assert first.cost_paid >= 0
    assert first.net_return <= first.gross_return or first.turnover == 0
