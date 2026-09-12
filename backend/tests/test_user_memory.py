from __future__ import annotations

from decimal import Decimal

import pytest

from signalos_backend.db import IntelligenceStore, build_engine
from signalos_backend.investment.personalization import LearnedPreference
from signalos_backend.users.memory import MemoryKind, MemorySource, UserMemoryStore


@pytest.mark.asyncio
async def test_memory_is_user_isolated_editable_and_learned_state_can_reset(tmp_path):
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}")
    intelligence_store = IntelligenceStore(engine)
    memories = UserMemoryStore(intelligence_store.sessions)
    await intelligence_store.create_schema()

    item = await memories.remember(
        user_id="user-a",
        kind=MemoryKind.EPISODIC,
        key="proposal_feedback",
        value={"proposal_id": "p-1", "reason": "too_risky"},
        source=MemorySource.EXPLICIT_FEEDBACK,
        confidence=Decimal("1"),
        evidence_count=1,
    )
    await memories.save_learned_preferences(
        user_id="user-a",
        preferences=(
            LearnedPreference(
                key="avoid_strategy_family",
                value="session_opening",
                confidence=Decimal("0.9"),
                evidence_count=6,
            ),
        ),
    )
    await memories.remember(
        user_id="user-b",
        kind=MemoryKind.EPISODIC,
        key="proposal_feedback",
        value={"proposal_id": "p-2", "reason": "not_interested"},
        source=MemorySource.EXPLICIT_FEEDBACK,
        confidence=Decimal("1"),
        evidence_count=1,
    )

    user_a = await memories.list(user_id="user-a")
    assert {memory.kind for memory in user_a} == {
        MemoryKind.EPISODIC,
        MemoryKind.LEARNED_PREFERENCE,
    }
    assert await memories.delete(user_id="user-b", memory_id=item.id) is False
    assert await memories.delete(user_id="user-a", memory_id=item.id) is True

    await memories.reset_learned_preferences(user_id="user-a")
    assert await memories.list(user_id="user-a") == ()
    assert len(await memories.list(user_id="user-b")) == 1

    await engine.dispose()
