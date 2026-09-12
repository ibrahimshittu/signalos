from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy


@dataclass(frozen=True)
class DeepResearchInput:
    run_id: str
    api_base_url: str
    operator_key: str


@dataclass(frozen=True)
class AccountSupervisionInput:
    account_id: str
    cadence_minutes: int = 15


@activity.defn
async def execute_research_run(payload: DeepResearchInput) -> str:
    """Call the API-owned intelligence service; retries are idempotent by run ID."""
    import httpx

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{payload.api_base_url}/v1/intelligence/runs/{payload.run_id}/execute",
            headers={"X-SignalOS-Admin-Key": payload.operator_key},
        )
        response.raise_for_status()
        return response.json()["status"]


@activity.defn
async def evaluate_account_policy(account_id: str) -> str:
    """Placeholder read/evaluate activity; it has no custody or execution credentials."""
    return f"evaluated:{account_id}"


@workflow.defn
class DeepResearchWorkflow:
    @workflow.run
    async def run(self, payload: DeepResearchInput) -> str:
        return await workflow.execute_activity(
            execute_research_run,
            payload,
            start_to_close_timeout=timedelta(minutes=20),
            schedule_to_close_timeout=timedelta(hours=4),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                backoff_coefficient=2,
                maximum_interval=timedelta(minutes=5),
                maximum_attempts=8,
            ),
        )


@workflow.defn
class AccountSupervisionWorkflow:
    """Durable, deterministic account supervision; no trade submission is present."""

    @workflow.run
    async def run(self, payload: AccountSupervisionInput) -> None:
        while True:
            await workflow.execute_activity(
                evaluate_account_policy,
                payload.account_id,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            await workflow.sleep(timedelta(minutes=payload.cadence_minutes))
