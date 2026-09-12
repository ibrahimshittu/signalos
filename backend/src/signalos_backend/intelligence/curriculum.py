from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CoverageDimension(StrEnum):
    ASSET = "asset"
    STRATEGY = "strategy"
    REGIME = "regime"
    TOOL = "tool"
    CONCEPT = "concept"


class CoverageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    dimension: CoverageDimension
    key: str
    evidence_count: int = Field(ge=0)
    verified_count: int = Field(ge=0)
    calibration_score: Decimal | None = Field(default=None, ge=0, le=1)
    verifier_failure_count: int = Field(default=0, ge=0)
    last_refreshed_at: datetime | None = None
    unresolved_contradictions: int = Field(default=0, ge=0)
    unanswered_user_questions: int = Field(default=0, ge=0)


class CurriculumTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    dimension: CoverageDimension
    key: str
    priority: int = Field(ge=1, le=100)
    objective: str
    reason: str
    allowed_action: str = "research_and_evaluate_only"


class CurriculumPlanner:
    """Schedules research gaps; it never edits skills, strategies, or active policy."""

    def plan(
        self,
        coverage: list[CoverageEntry],
        *,
        now: datetime | None = None,
    ) -> list[CurriculumTask]:
        now = now or datetime.now(UTC)
        tasks: list[CurriculumTask] = []
        for entry in coverage:
            reasons: list[str] = []
            priority = 10
            if entry.verified_count < 3:
                reasons.append("insufficient verified evidence")
                priority += 25
            if not entry.last_refreshed_at or now - entry.last_refreshed_at > timedelta(days=7):
                reasons.append("knowledge is stale")
                priority += 20
            if entry.verifier_failure_count >= 3:
                reasons.append("repeated verifier failures")
                priority += 20
            if entry.unresolved_contradictions:
                reasons.append("unresolved contradictory evidence")
                priority += min(20, entry.unresolved_contradictions * 5)
            if entry.unanswered_user_questions:
                reasons.append("unanswered user questions")
                priority += min(15, entry.unanswered_user_questions * 3)
            if reasons:
                tasks.append(
                    CurriculumTask(
                        dimension=entry.dimension,
                        key=entry.key,
                        priority=min(100, priority),
                        objective=f"Improve verified coverage for {entry.key}.",
                        reason="; ".join(reasons),
                    )
                )
        return sorted(tasks, key=lambda item: item.priority, reverse=True)
