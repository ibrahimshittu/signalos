from __future__ import annotations

import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from signalos_backend.brokers.domain import BrokerEnvironment
from signalos_backend.domain import StrategyStatus
from signalos_backend.investment.pipeline import PipelineRunSummary
from signalos_backend.market.domain import (
    MarketAnalysisRequest,
    MarketAnalysisRequestStatus,
    MarketScan,
    MarketScanResult,
)
from signalos_backend.market.sessions import SessionName, SweepOffset
from signalos_backend.market.worker import run_scan_loop
from signalos_backend.seeds import build_strategy_registry


@pytest.fixture(autouse=True)
def _disable_live_telemetry(monkeypatch) -> None:
    monkeypatch.setattr(
        "signalos_backend.market.worker.logfire.info",
        lambda _message, **_attributes: None,
    )


class OneScanService:
    def __init__(self, requests: tuple[MarketAnalysisRequest, ...] = ()) -> None:
        self.requests = requests
        self.completed: list[tuple[tuple[MarketAnalysisRequest, ...], str]] = []

    async def claim_analysis_requests(self, *, environment, limit=100):
        del environment, limit
        requests, self.requests = self.requests, ()
        return requests

    async def complete_analysis_requests(self, *, requests, scan_id):
        self.completed.append((requests, scan_id))

    async def fail_analysis_requests(self, *, requests, error_code):
        raise AssertionError(f"unexpected failure: {requests=} {error_code=}")

    async def run_scan(self, *, environment):
        return MarketScan(
            id="scan-1",
            environment=environment,
            source_count=426,
            observed_at=datetime(2026, 7, 15, 7, 15, tzinfo=UTC),
            created_at=datetime(2026, 7, 15, 7, 15, tzinfo=UTC),
            result=MarketScanResult(hot_universe=(), agent_shortlist=()),
        )


class CapturingPipeline:
    def __init__(self) -> None:
        self.session_sweeps = ()
        self.strategies = build_strategy_registry()
        self.intelligence_store = SimpleNamespace(load_governance=AsyncMock(return_value=([], [])))

    async def analyze_scan(self, scan, *, session_sweeps=()):
        self.session_sweeps = session_sweeps
        return PipelineRunSummary(
            scan_id=scan.id,
            approved_strategies=0,
            candidates_considered=0,
            strategy_matches=0,
            signals_found=0,
            analysis_completed=0,
            no_trade_decisions=0,
            proposals_created=0,
            duplicates_skipped=0,
            gate_rejections=0,
            model_available=False,
        )


@pytest.mark.asyncio
async def test_worker_runs_analysis_and_passes_due_session_windows() -> None:
    pipeline = CapturingPipeline()
    strategy = pipeline.strategies.list_latest()[0]
    pipeline.strategies.restore(strategy.id, strategy.model_copy(update={
        "status": StrategyStatus.APPROVED,
    }))
    pipeline.intelligence_store.load_governance.return_value = ([strategy], [])

    await run_scan_loop(
        OneScanService(),
        environment=BrokerEnvironment.MAINNET,
        interval_seconds=60,
        pipeline=pipeline,
        once=True,
    )

    assert [(sweep.session, sweep.offset) for sweep in pipeline.session_sweeps] == [
        (SessionName.LONDON, SweepOffset.POST_15)
    ]
    assert pipeline.strategies.approved() == []


@pytest.mark.asyncio
async def test_worker_logs_an_actionable_analysis_outcome(caplog, monkeypatch) -> None:
    telemetry: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "signalos_backend.market.worker.logfire.info",
        lambda message, **attributes: telemetry.append((message, attributes)),
    )
    with caplog.at_level(logging.INFO, logger="signalos_backend.market.worker"):
        await run_scan_loop(
            OneScanService(),
            environment=BrokerEnvironment.MAINNET,
            interval_seconds=60,
            pipeline=CapturingPipeline(),
            once=True,
        )

    assert "approved_strategies=0" in caplog.text
    assert "strategy_matches=0" in caplog.text
    assert "proposals=0" in caplog.text
    assert telemetry[-1] == (
        "investment analysis completed",
        {
            "scan_id": "scan-1",
            "approved_strategies": 0,
            "candidates_considered": 0,
            "strategy_matches": 0,
            "signals_found": 0,
            "analysis_completed": 0,
            "no_trade_decisions": 0,
            "proposals_created": 0,
            "duplicates_skipped": 0,
            "gate_rejections": 0,
            "model_available": False,
        },
    )


@pytest.mark.asyncio
async def test_manual_request_forces_a_deep_review_and_is_completed() -> None:
    request = MarketAnalysisRequest(
        id="analysis-1",
        environment=BrokerEnvironment.MAINNET,
        status=MarketAnalysisRequestStatus.RUNNING,
        requested_at=datetime(2026, 8, 17, 9, tzinfo=UTC),
        started_at=datetime(2026, 8, 17, 9, tzinfo=UTC),
    )
    service = OneScanService((request,))
    pipeline = CapturingPipeline()

    await run_scan_loop(
        service,
        environment=BrokerEnvironment.MAINNET,
        interval_seconds=60,
        pipeline=pipeline,
        analysis_interval_seconds=300,
        once=True,
    )

    assert service.completed == [((request,), "scan-1")]
