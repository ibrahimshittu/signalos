from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from signalos_backend.config import Settings
from signalos_backend.db import IntelligenceStore
from signalos_backend.domain import (
    Citation,
    ClaimKind,
    IntelligenceReport,
    QuantitativeSnapshot,
    QuestionRequest,
    QuestionRun,
    RunEvent,
)
from signalos_backend.intelligence.agents import (
    AgentDeps,
    ProducedAnalysis,
    build_agents,
    deterministic_producer,
    deterministic_verifier,
)
from signalos_backend.intelligence.evidence import EvidenceGraph
from signalos_backend.intelligence.laboratory import DeterministicExperimentRunner
from signalos_backend.intelligence.registries import SkillRegistry, StrategyRegistry, ToolRegistry


class IntelligenceService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: IntelligenceStore,
        evidence: EvidenceGraph,
        strategies: StrategyRegistry,
        skills: SkillRegistry,
        tools: ToolRegistry,
    ) -> None:
        self.settings = settings
        self.store = store
        self.evidence = evidence
        self.strategies = strategies
        self.skills = skills
        self.tools = tools
        self.agents = build_agents(settings, skills)
        self.deep_dispatcher: Callable[[UUID], Awaitable[None]] | None = None
        self.experiment_runner = DeterministicExperimentRunner()

    async def ask(self, request: QuestionRequest) -> QuestionRun:
        run = QuestionRun(request=request, status="queued")
        await self.store.save_run(run)
        await self._event(run.id, 0, "queued", "Research request accepted.")
        if request.mode == "fast":
            await self.execute(run.id)
            return (await self.store.get_run(run.id)) or run
        if self.deep_dispatcher is not None:
            await self.deep_dispatcher(run.id)
        return run

    async def execute(self, run_id: UUID) -> QuestionRun:
        run = await self.store.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        if run.status in {"published", "rejected"}:
            return run
        researching = run.model_copy(
            update={"status": "researching", "updated_at": datetime.now(UTC)}
        )
        await self.store.save_run(researching)
        await self._event(run_id, 1, "routing", "Relevant evidence and capabilities selected.")
        claims = self.evidence.search(
            run.request.question,
            entity_ids=run.request.context_entity_ids,
        )
        await self._event(run_id, 2, "research", f"Found {len(claims)} admitted claims.")
        analysis = await self._produce(run.request.question, claims, run.request.account_id)
        verifying = researching.model_copy(
            update={"status": "verifying", "updated_at": datetime.now(UTC)}
        )
        await self.store.save_run(verifying)
        await self._event(run_id, 3, "verification", "Independent evidence verification started.")
        verification = await self._verify(analysis, claims, run.request.account_id)
        if not verification.accepted:
            rejected = verifying.model_copy(
                update={"status": "rejected", "updated_at": datetime.now(UTC)}
            )
            await self.store.save_run(rejected)
            await self._event(run_id, 4, "failed", "; ".join(verification.reasons))
            return rejected
        report = self._report(run_id, run.request.question, analysis, claims)
        if run.request.account_id is None:  # pragma: no cover - API/worker contract violation
            raise RuntimeError("intelligence run has no owning user")
        await self.store.save_report(report, user_id=run.request.account_id)
        published = verifying.model_copy(
            update={
                "status": "published",
                "report_id": report.id,
                "updated_at": datetime.now(UTC),
            }
        )
        await self.store.save_run(published)
        await self._event(run_id, 4, "published", "Verified report published.")
        return published

    async def _produce(self, question, claims, account_id) -> ProducedAnalysis:
        if self.agents is None:
            return deterministic_producer(question, claims)
        producer, _ = self.agents
        evidence_packet = "\n".join(
            f"CLAIM {claim.id} [{claim.kind.value}]: {claim.text}" for claim in claims
        )
        result = await producer.run(
            f"Question: {question}\nAdmitted evidence:\n{evidence_packet}",
            deps=AgentDeps(admitted_claims=tuple(claims), account_id=account_id),
        )
        return result.output

    async def _verify(self, analysis, claims, account_id):
        deterministic = deterministic_verifier(analysis, claims)
        if not deterministic.accepted or self.agents is None:
            return deterministic
        _, verifier = self.agents
        evidence_packet = "\n".join(
            f"CLAIM {claim.id} [{claim.kind.value}]: {claim.text}" for claim in claims
        )
        result = await verifier.run(
            f"Verify this analysis:\n{analysis.model_dump_json()}\nEvidence:\n{evidence_packet}",
            deps=AgentDeps(admitted_claims=tuple(claims), account_id=account_id),
        )
        return result.output

    def _report(self, run_id, question, analysis, claims) -> IntelligenceReport:
        selected = [claim for claim in claims if str(claim.id) in analysis.claim_ids]
        citations = tuple(
            Citation(claim_id=claim.id, source_id=source_id, label=claim.kind.value)
            for claim in selected
            for source_id in claim.source_ids
        )
        timestamps = [
            self.evidence.sources[source_id].retrieved_at
            for claim in selected
            for source_id in claim.source_ids
        ]
        quality = self.evidence.quality([claim.id for claim in selected])
        return IntelligenceReport(
            id=uuid5(NAMESPACE_URL, f"signalos-report:{run_id}"),
            question_id=run_id,
            title=question[:160],
            executive_view=analysis.executive_view,
            what_changed=analysis.what_changed,
            verified_facts=analysis.verified_facts,
            quantitative_snapshot=QuantitativeSnapshot(metrics={"evidence_items": len(selected)}),
            strategy_interpretations=analysis.strategy_interpretations,
            bull_scenario=analysis.bull_scenario,
            base_scenario=analysis.base_scenario,
            bear_scenario=analysis.bear_scenario,
            portfolio_relevance=analysis.portfolio_relevance,
            drivers=analysis.drivers,
            risks_and_thesis_breakers=analysis.risks_and_thesis_breakers,
            monitoring_questions=analysis.monitoring_questions,
            evidence_quality=quality,
            source_coverage=Decimal("1") if selected else Decimal("0"),
            citations=citations,
            data_as_of=max(timestamps) if timestamps else datetime.now(UTC),
            model_versions={
                "producer": self.settings.producer_model
                if self.agents
                else "deterministic-fallback",
                "verifier": self.settings.verifier_model
                if self.agents
                else "deterministic-verifier",
            },
            skill_versions={item.stable_id: item.version for item in self.skills.list_latest()},
            tool_versions={item.stable_id: "1.0.0" for item in self.tools.public()},
            prompt_version="intelligence-base-1.0.0",
            evidence_version="evidence-graph-1.0.0",
            policy_version="portfolio-policy-1.0.0",
            limitations=analysis.limitations,
            disputed_claims=tuple(
                claim.text for claim in selected if claim.kind is ClaimKind.UNKNOWN
            ),
        )

    async def _event(self, run_id, sequence, kind, message) -> None:
        await self.store.append_event(
            RunEvent(run_id=run_id, sequence=sequence, kind=kind, message=message)
        )
