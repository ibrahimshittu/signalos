from __future__ import annotations

import hmac
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from signalos_backend.domain import (
    EvidenceClaim,
    QuestionRequest,
    SkillManifest,
    SourceTier,
    StrategySpec,
    StrategyStatus,
)
from signalos_backend.identity import Principal, require_principal
from signalos_backend.intelligence.laboratory import ExperimentSpec
from signalos_backend.intelligence.promotion import ShadowEvidence, assess_promotion
from signalos_backend.intelligence.service import IntelligenceService

router = APIRouter(prefix="/v1")


def get_service(request: Request) -> IntelligenceService:
    return request.app.state.service


def require_operator(
    request: Request,
    x_signalos_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    if x_signalos_admin_key is None or not hmac.compare_digest(
        x_signalos_admin_key,
        request.app.state.settings.api_key.get_secret_value(),
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="operator authorization required"
        )


class SourceIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    uri: str
    title: str
    tier: SourceTier
    content: str = Field(min_length=1, max_length=100_000)
    published_at: datetime | None = None


class UserQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=5, max_length=4_000)
    context_entity_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=30)
    mode: Literal["fast", "deep"] = "fast"


@router.post("/intelligence/questions", status_code=status.HTTP_202_ACCEPTED)
async def ask_question(
    payload: UserQuestionRequest,
    principal: Annotated[Principal, Depends(require_principal)],
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    return await service.ask(
        QuestionRequest(
            question=payload.question,
            account_id=principal.user_id,
            context_entity_ids=payload.context_entity_ids,
            mode=payload.mode,
        )
    )


@router.get("/intelligence/questions/{run_id}")
async def get_question(
    run_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    result = await service.store.get_run(run_id)
    if result is None or result.request.account_id != principal.user_id:
        raise HTTPException(status_code=404, detail="question run not found")
    return result


@router.get("/intelligence/runs/{run_id}")
async def get_run(
    run_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    result = await service.store.get_run(run_id)
    if result is None or result.request.account_id != principal.user_id:
        raise HTTPException(status_code=404, detail="question run not found")
    return result


@router.get("/intelligence/questions/{run_id}/events")
async def get_question_events(
    run_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    result = await service.store.get_run(run_id)
    if result is None or result.request.account_id != principal.user_id:
        raise HTTPException(status_code=404, detail="question run not found")
    return await service.store.events(run_id)


@router.post("/intelligence/runs/{run_id}/execute", dependencies=[Depends(require_operator)])
async def execute_run(
    run_id: UUID,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    try:
        return await service.execute(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="question run not found") from exc


@router.get("/intelligence/reports")
async def list_reports(
    principal: Annotated[Principal, Depends(require_principal)],
    service: Annotated[IntelligenceService, Depends(get_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await service.store.list_reports(user_id=principal.user_id, limit=limit)


@router.get("/intelligence/reports/{report_id}")
async def get_report(
    report_id: UUID,
    principal: Annotated[Principal, Depends(require_principal)],
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    report = await service.store.get_report(report_id, user_id=principal.user_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report


@router.get("/intelligence/claims/{claim_id}")
async def get_claim(
    claim_id: UUID,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    claim = service.evidence.claims.get(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return claim


@router.get("/intelligence/sources/{source_id}")
async def get_source(
    source_id: UUID,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    source = service.evidence.sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")
    return source


@router.post("/admin/evidence/sources", dependencies=[Depends(require_operator)])
async def ingest_source(
    payload: SourceIngestRequest,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    source = service.evidence.ingest_source(**payload.model_dump())
    await service.store.save_source(source)
    return source


@router.post("/admin/evidence/sources/{source_id}/verify", dependencies=[Depends(require_operator)])
async def verify_source(
    source_id: UUID,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    try:
        source = service.evidence.verify_source(source_id)
        await service.store.save_source(source)
        return source
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="source not found") from exc


@router.post("/admin/evidence/claims", dependencies=[Depends(require_operator)])
async def propose_claim(
    payload: EvidenceClaim,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    claim = service.evidence.propose_claim(payload)
    await service.store.save_claim(claim)
    return claim


@router.post("/admin/evidence/claims/{claim_id}/admit", dependencies=[Depends(require_operator)])
async def admit_claim(
    claim_id: UUID,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    try:
        claim = service.evidence.admit_claim(claim_id)
        await service.store.save_claim(claim)
        return claim
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/strategies")
async def list_strategies(service: Annotated[IntelligenceService, Depends(get_service)]):
    return service.strategies.list_latest()


@router.get("/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: str,
    service: Annotated[IntelligenceService, Depends(get_service)],
    version: str | None = None,
):
    try:
        return service.strategies.get(strategy_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="strategy not found") from exc


@router.get("/strategies/{strategy_id}/evaluations")
async def get_strategy_evaluations(
    strategy_id: str,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    return {
        "strategy_id": strategy_id,
        "evaluations": await service.store.list_evaluations(strategy_id),
    }


@router.post("/admin/strategies", dependencies=[Depends(require_operator)])
async def register_strategy_candidate(
    payload: StrategySpec,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    strategy = service.strategies.register_candidate(payload)
    await service.store.save_strategy(strategy)
    return strategy


@router.post(
    "/admin/strategies/{strategy_id}/evaluations",
    dependencies=[Depends(require_operator)],
)
async def evaluate_strategy(
    strategy_id: str,
    payload: ExperimentSpec,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    try:
        strategy = service.strategies.get(strategy_id, payload.strategy_version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="strategy not found") from exc
    result = service.experiment_runner.run(strategy, payload)
    await service.store.save_evaluation(result)
    return result


@router.post(
    "/admin/strategies/{strategy_id}/{version}/transition", dependencies=[Depends(require_operator)]
)
async def transition_strategy(
    strategy_id: str,
    version: str,
    target: StrategyStatus,
    service: Annotated[IntelligenceService, Depends(get_service)],
    shadow: ShadowEvidence | None = None,
):
    try:
        current = service.strategies.get(strategy_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="strategy not found") from exc
    if target in {
        StrategyStatus.VALIDATED,
        StrategyStatus.SHADOW,
        StrategyStatus.PROMOTION_PENDING,
        StrategyStatus.APPROVED,
    }:
        evaluation = await service.store.latest_evaluation(strategy_id, version)
        if evaluation is None or not evaluation.passed_gates:
            raise HTTPException(status_code=409, detail="passing version-bound evaluation required")
        if f"evaluation:{evaluation.reproducibility_hash}" not in current.evidence_references:
            raise HTTPException(
                status_code=409, detail="strategy must reference its exact evaluation"
            )
        if target in {StrategyStatus.PROMOTION_PENDING, StrategyStatus.APPROVED}:
            if shadow is None:
                raise HTTPException(status_code=409, detail="shadow evidence is required")
            assessment = assess_promotion(current, evaluation, shadow)
            if not assessment.eligible_for_operator_review:
                raise HTTPException(status_code=409, detail=", ".join(assessment.failures))
    try:
        strategy = service.strategies.transition(
            strategy_id, version, target, operator_approved=target is StrategyStatus.APPROVED
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await service.store.save_strategy(strategy)
    return strategy


@router.get("/skills")
async def list_skills(service: Annotated[IntelligenceService, Depends(get_service)]):
    return service.skills.list_latest()


@router.get("/skills/{skill_id}")
async def get_skill(
    skill_id: str,
    service: Annotated[IntelligenceService, Depends(get_service)],
    version: str | None = None,
):
    try:
        return service.skills.get(skill_id, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="skill not found") from exc


@router.post("/admin/skills", dependencies=[Depends(require_operator)])
async def register_skill_candidate(
    payload: SkillManifest,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    skill = service.skills.register_candidate(payload)
    await service.store.save_skill(skill)
    return skill


@router.post(
    "/admin/skills/{skill_id}/{version}/promote",
    dependencies=[Depends(require_operator)],
)
async def promote_skill(
    skill_id: str,
    version: str,
    service: Annotated[IntelligenceService, Depends(get_service)],
):
    skill = service.skills.promote(skill_id, version, operator_approved=True)
    await service.store.save_skill(skill)
    return skill


@router.get("/tools")
async def list_tools(service: Annotated[IntelligenceService, Depends(get_service)]):
    return service.tools.public()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "signalos-backend"}
