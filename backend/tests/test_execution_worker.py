from __future__ import annotations

from signalos_backend.brokers.domain import BrokerEnvironment
from signalos_backend.execution.reconciliation import ReconciliationSummary
from signalos_backend.execution.worker import run_reconciliation_loop


async def test_reconciliation_worker_runs_one_complete_cycle_without_sleeping() -> None:
    calls: list[BrokerEnvironment] = []

    class Service:
        async def run_once(self, *, environment):
            calls.append(environment)
            return ReconciliationSummary(
                accounts_reconciled=1,
                accounts_failed=0,
                orders_reconciled=1,
                executions_seen=1,
                open_positions=1,
            )

    async def fail_if_slept(delay: float) -> None:  # pragma: no cover
        raise AssertionError(delay)

    await run_reconciliation_loop(
        Service(),
        environment=BrokerEnvironment.MAINNET,
        interval_seconds=5,
        once=True,
        sleep=fail_if_slept,
    )

    assert calls == [BrokerEnvironment.MAINNET]
