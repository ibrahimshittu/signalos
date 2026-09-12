from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from signalos_backend.domain import (
    EvidenceClaim,
    EvidenceSource,
    IntelligenceReport,
    QuestionRun,
    RunEvent,
    SkillManifest,
    StrategySpec,
)
from signalos_backend.intelligence.laboratory import ExperimentResult


class Base(DeclarativeBase):
    pass


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    account_id: Mapped[str | None] = mapped_column(String(200), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[str] = mapped_column(Text)


class EventRecord(Base):
    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[str] = mapped_column(Text)


class IntelligenceStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def save_run(self, run: QuestionRun) -> None:
        async with self.sessions() as session:
            record = await session.get(DocumentRecord, str(run.id))
            if record is None:
                record = DocumentRecord(
                    id=str(run.id),
                    kind="question_run",
                    status=run.status,
                    account_id=run.request.account_id,
                    created_at=run.created_at,
                    updated_at=run.updated_at,
                    payload=run.model_dump_json(),
                )
                session.add(record)
            else:
                record.status = run.status
                record.updated_at = run.updated_at
                record.payload = run.model_dump_json()
            await session.commit()

    async def _save_document(
        self,
        *,
        document_id: UUID,
        kind: str,
        status: str,
        created_at: datetime,
        payload: str,
        account_id: str | None = None,
    ) -> None:
        async with self.sessions() as session:
            record = await session.get(DocumentRecord, str(document_id))
            if record is None:
                session.add(
                    DocumentRecord(
                        id=str(document_id),
                        kind=kind,
                        status=status,
                        account_id=account_id,
                        created_at=created_at,
                        updated_at=created_at,
                        payload=payload,
                    )
                )
            else:
                if record.kind != kind:
                    raise ValueError(f"document {document_id} has conflicting kind")
                record.status = status
                record.updated_at = created_at
                record.payload = payload
            await session.commit()

    async def save_source(self, source: EvidenceSource) -> None:
        await self._save_document(
            document_id=source.id,
            kind="evidence_source",
            status="verified" if source.verified else "quarantined",
            created_at=source.retrieved_at,
            payload=source.model_dump_json(),
        )

    async def save_claim(self, claim: EvidenceClaim) -> None:
        await self._save_document(
            document_id=claim.id,
            kind="evidence_claim",
            status="admitted" if claim.admitted else "quarantined",
            created_at=claim.valid_from or datetime.now(UTC),
            payload=claim.model_dump_json(),
        )

    async def load_evidence(self) -> tuple[list[EvidenceSource], list[EvidenceClaim]]:
        async with self.sessions() as session:
            statement = select(DocumentRecord).where(
                DocumentRecord.kind.in_(("evidence_source", "evidence_claim"))
            )
            records = (await session.scalars(statement)).all()
        sources = [
            EvidenceSource.model_validate_json(record.payload)
            for record in records
            if record.kind == "evidence_source"
        ]
        claims = [
            EvidenceClaim.model_validate_json(record.payload)
            for record in records
            if record.kind == "evidence_claim"
        ]
        return sources, claims

    async def save_evaluation(self, evaluation: ExperimentResult) -> None:
        evaluation_id = uuid5(
            NAMESPACE_URL,
            f"evaluation:{evaluation.strategy_id}:{evaluation.strategy_version}:"
            f"{evaluation.reproducibility_hash}",
        )
        await self._save_document(
            document_id=evaluation_id,
            kind="strategy_evaluation",
            status="passed" if evaluation.passed_gates else "failed",
            created_at=datetime.now(UTC),
            payload=evaluation.model_dump_json(),
        )

    async def list_evaluations(self, strategy_id: str) -> list[ExperimentResult]:
        async with self.sessions() as session:
            statement = (
                select(DocumentRecord)
                .where(DocumentRecord.kind == "strategy_evaluation")
                .order_by(DocumentRecord.created_at.desc())
            )
            records = (await session.scalars(statement)).all()
        evaluations = [ExperimentResult.model_validate_json(record.payload) for record in records]
        return [item for item in evaluations if item.strategy_id == strategy_id]

    async def latest_evaluation(
        self, strategy_id: str, strategy_version: str
    ) -> ExperimentResult | None:
        evaluations = await self.list_evaluations(strategy_id)
        return next(
            (
                evaluation
                for evaluation in evaluations
                if evaluation.strategy_version == strategy_version
            ),
            None,
        )

    async def save_strategy(self, strategy: StrategySpec) -> None:
        strategy_id = uuid5(NAMESPACE_URL, f"strategy:{strategy.id}:{strategy.version}")
        await self._save_document(
            document_id=strategy_id,
            kind="strategy",
            status=strategy.status,
            created_at=strategy.created_at,
            payload=strategy.model_dump_json(),
        )

    async def get_strategy(self, strategy_id: str, version: str) -> StrategySpec | None:
        document_id = uuid5(NAMESPACE_URL, f"strategy:{strategy_id}:{version}")
        async with self.sessions() as session:
            record = await session.get(DocumentRecord, str(document_id))
            return StrategySpec.model_validate_json(record.payload) if record else None

    async def save_skill(self, skill: SkillManifest) -> None:
        skill_id = uuid5(NAMESPACE_URL, f"skill:{skill.stable_id}:{skill.version}")
        await self._save_document(
            document_id=skill_id,
            kind="skill",
            status=skill.status,
            created_at=skill.effective_at or datetime.now(UTC),
            payload=skill.model_dump_json(),
        )

    async def load_governance(self) -> tuple[list[StrategySpec], list[SkillManifest]]:
        async with self.sessions() as session:
            statement = select(DocumentRecord).where(DocumentRecord.kind.in_(("strategy", "skill")))
            records = (await session.scalars(statement)).all()
        strategies = [
            StrategySpec.model_validate_json(record.payload)
            for record in records
            if record.kind == "strategy"
        ]
        skills = [
            SkillManifest.model_validate_json(record.payload)
            for record in records
            if record.kind == "skill"
        ]
        return strategies, skills

    async def get_run(self, run_id: UUID) -> QuestionRun | None:
        async with self.sessions() as session:
            record = await session.get(DocumentRecord, str(run_id))
            return QuestionRun.model_validate_json(record.payload) if record else None

    async def save_report(self, report: IntelligenceReport, *, user_id: str) -> None:
        await self._save_document(
            document_id=report.id,
            kind="report",
            status="published",
            created_at=report.published_at,
            payload=report.model_dump_json(),
            account_id=user_id,
        )

    async def get_report(self, report_id: UUID, *, user_id: str) -> IntelligenceReport | None:
        async with self.sessions() as session:
            record = await session.get(DocumentRecord, str(report_id))
            if not record or record.kind != "report" or record.account_id != user_id:
                return None
            return IntelligenceReport.model_validate_json(record.payload)

    async def list_reports(self, *, user_id: str, limit: int = 50) -> list[IntelligenceReport]:
        async with self.sessions() as session:
            statement = (
                select(DocumentRecord)
                .where(
                    DocumentRecord.kind == "report",
                    DocumentRecord.account_id == user_id,
                )
                .order_by(DocumentRecord.created_at.desc())
                .limit(limit)
            )
            records = (await session.scalars(statement)).all()
            return [IntelligenceReport.model_validate_json(record.payload) for record in records]

    async def append_event(self, event: RunEvent) -> None:
        async with self.sessions() as session:
            existing = await session.scalar(
                select(EventRecord).where(
                    EventRecord.run_id == str(event.run_id),
                    EventRecord.sequence == event.sequence,
                )
            )
            if existing is not None:
                return
            session.add(
                EventRecord(
                    id=str(event.id),
                    run_id=str(event.run_id),
                    sequence=event.sequence,
                    kind=event.kind,
                    created_at=event.created_at,
                    payload=event.model_dump_json(),
                )
            )
            await session.commit()

    async def events(self, run_id: UUID) -> list[RunEvent]:
        async with self.sessions() as session:
            statement = (
                select(EventRecord)
                .where(EventRecord.run_id == str(run_id))
                .order_by(EventRecord.sequence)
            )
            records = (await session.scalars(statement)).all()
            return [RunEvent.model_validate_json(record.payload) for record in records]


def build_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


async def session_dependency(store: IntelligenceStore) -> AsyncIterator[AsyncSession]:
    async with store.sessions() as session:
        yield session
