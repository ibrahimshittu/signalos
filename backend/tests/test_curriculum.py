from datetime import UTC, datetime, timedelta

from signalos_backend.intelligence.curriculum import (
    CoverageDimension,
    CoverageEntry,
    CurriculumPlanner,
)


def test_curriculum_prioritizes_stale_contradictory_gaps_without_mutation_authority():
    tasks = CurriculumPlanner().plan(
        [
            CoverageEntry(
                dimension=CoverageDimension.ASSET,
                key="BTC",
                evidence_count=2,
                verified_count=1,
                last_refreshed_at=datetime.now(UTC) - timedelta(days=30),
                unresolved_contradictions=3,
                unanswered_user_questions=2,
            )
        ]
    )
    assert tasks[0].priority >= 70
    assert tasks[0].allowed_action == "research_and_evaluate_only"
