import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from signalos_backend.config import get_settings
from signalos_backend.temporal.workflows import (
    AccountSupervisionWorkflow,
    DeepResearchWorkflow,
    evaluate_account_policy,
    execute_research_run,
)


async def main() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    worker = Worker(
        client,
        task_queue=settings.temporal_research_queue,
        workflows=[DeepResearchWorkflow, AccountSupervisionWorkflow],
        activities=[execute_research_run, evaluate_account_policy],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
