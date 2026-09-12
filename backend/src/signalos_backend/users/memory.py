from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, DateTime, Integer, Numeric, String, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from signalos_backend.db import Base
from signalos_backend.investment.personalization import LearnedPreference


class MemoryKind(StrEnum):
    ACCOUNT = "account"
    EPISODIC = "episodic"
    LEARNED_PREFERENCE = "learned_preference"


class MemorySource(StrEnum):
    ACCOUNT_SYNC = "account_sync"
    EXPLICIT_FEEDBACK = "explicit_feedback"
    BEHAVIOR_INFERENCE = "behavior_inference"


class UserMemory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    user_id: str
    kind: MemoryKind
    key: str
    value: dict[str, Any]
    source: MemorySource
    confidence: Decimal = Field(ge=0, le=1)
    evidence_count: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None


class UserMemoryRecord(Base):
    __tablename__ = "user_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    evidence_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class UserMemoryStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def remember(
        self,
        *,
        user_id: str,
        kind: MemoryKind,
        key: str,
        value: dict[str, Any],
        source: MemorySource,
        confidence: Decimal,
        evidence_count: int,
        expires_at: datetime | None = None,
    ) -> UserMemory:
        now = datetime.now(UTC)
        record = UserMemoryRecord(
            id=str(uuid4()),
            user_id=user_id,
            kind=kind.value,
            key=key,
            value=value,
            source=source.value,
            confidence=confidence,
            evidence_count=evidence_count,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        async with self.sessions() as session:
            session.add(record)
            await session.commit()
        return self._domain(record)

    async def list(
        self, *, user_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[UserMemory, ...]:
        async with self.sessions() as session:
            records = (
                await session.scalars(
                    select(UserMemoryRecord)
                    .where(UserMemoryRecord.user_id == user_id)
                    .order_by(UserMemoryRecord.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
            return tuple(self._domain(record) for record in records)

    async def delete(self, *, user_id: str, memory_id: UUID) -> bool:
        async with self.sessions() as session:
            record = await session.scalar(
                select(UserMemoryRecord).where(
                    UserMemoryRecord.id == str(memory_id),
                    UserMemoryRecord.user_id == user_id,
                )
            )
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
            return True

    async def save_learned_preferences(
        self, *, user_id: str, preferences: tuple[LearnedPreference, ...]
    ) -> None:
        await self.reset_learned_preferences(user_id=user_id)
        for preference in preferences:
            await self.remember(
                user_id=user_id,
                kind=MemoryKind.LEARNED_PREFERENCE,
                key=preference.key,
                value={"value": preference.value},
                source=MemorySource.BEHAVIOR_INFERENCE,
                confidence=preference.confidence,
                evidence_count=preference.evidence_count,
            )

    async def reset_learned_preferences(self, *, user_id: str) -> None:
        async with self.sessions() as session:
            await session.execute(
                delete(UserMemoryRecord).where(
                    UserMemoryRecord.user_id == user_id,
                    UserMemoryRecord.kind == MemoryKind.LEARNED_PREFERENCE.value,
                )
            )
            await session.commit()

    @staticmethod
    def _domain(record: UserMemoryRecord) -> UserMemory:
        return UserMemory(
            id=UUID(record.id),
            user_id=record.user_id,
            kind=record.kind,
            key=record.key,
            value=record.value,
            source=record.source,
            confidence=record.confidence,
            evidence_count=record.evidence_count,
            created_at=record.created_at,
            updated_at=record.updated_at,
            expires_at=record.expires_at,
        )
