from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    and_,
    delete,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from signalos_backend.brokers.domain import BrokerEnvironment
from signalos_backend.db import Base, DocumentRecord
from signalos_backend.market.domain import (
    Instrument,
    MarketAnalysisRequest,
    MarketAnalysisRequestStatus,
    MarketCandidate,
    MarketCategory,
    MarketReview,
    MarketReviewCandidate,
    MarketReviewStatus,
    MarketScan,
    MarketScanResult,
    PortfolioReviewOutcome,
    TickerSnapshot,
)


class MarketInstrumentRecord(Base):
    __tablename__ = "market_instruments"

    environment: Mapped[str] = mapped_column(String(20), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40), primary_key=True)
    base_coin: Mapped[str] = mapped_column(String(30), index=True)
    quote_coin: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(30, 16))
    quantity_step: Mapped[Decimal] = mapped_column(Numeric(30, 16))
    minimum_order_quantity: Mapped[Decimal] = mapped_column(Numeric(30, 16))
    minimum_notional: Mapped[Decimal] = mapped_column(Numeric(30, 16))
    funding_interval_minutes: Mapped[int | None] = mapped_column(Integer)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MarketTickerRecord(Base):
    __tablename__ = "market_latest_tickers"

    environment: Mapped[str] = mapped_column(String(20), primary_key=True)
    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_price: Mapped[Decimal] = mapped_column(Numeric(30, 16))
    bid_price: Mapped[Decimal] = mapped_column(Numeric(30, 16))
    ask_price: Mapped[Decimal] = mapped_column(Numeric(30, 16))
    turnover_24h: Mapped[Decimal] = mapped_column(Numeric(38, 12), index=True)
    volume_24h: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    price_change_24h: Mapped[Decimal] = mapped_column(Numeric(20, 12))
    open_interest: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    funding_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    next_funding_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class MarketScanRunRecord(Base):
    __tablename__ = "market_scan_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    environment: Mapped[str] = mapped_column(String(20), index=True)
    source_count: Mapped[int] = mapped_column(Integer)
    hot_count: Mapped[int] = mapped_column(Integer)
    shortlist_count: Mapped[int] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    analysis_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    approved_strategy_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidates_considered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategy_matches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signals_found: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analyses_completed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    no_trade_decisions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposals_created: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplicates_skipped: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gate_rejections: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class MarketCandidateRecord(Base):
    __tablename__ = "market_scan_candidates"

    scan_id: Mapped[str] = mapped_column(
        ForeignKey("market_scan_runs.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer)
    selected_for_agent: Mapped[bool] = mapped_column(Boolean, index=True)
    activity_score: Mapped[Decimal] = mapped_column(Numeric(20, 12))
    turnover_24h: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    price_change_24h: Mapped[Decimal] = mapped_column(Numeric(20, 12))
    spread_bps: Mapped[Decimal] = mapped_column(Numeric(20, 12))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_strategy_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class MarketAnalysisRequestRecord(Base):
    __tablename__ = "market_analysis_requests"
    __table_args__ = (
        Index(
            "uq_market_analysis_requests_active_user_environment",
            "user_id",
            "environment",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    environment: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scan_id: Mapped[str | None] = mapped_column(
        ForeignKey("market_scan_runs.id", ondelete="SET NULL"), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class MarketStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def replace_instruments(
        self,
        *,
        environment: BrokerEnvironment,
        instruments: tuple[Instrument, ...],
        refreshed_at: datetime,
    ) -> None:
        async with self.sessions() as session:
            await session.execute(
                delete(MarketInstrumentRecord).where(
                    MarketInstrumentRecord.environment == environment.value
                )
            )
            session.add_all(
                [
                    MarketInstrumentRecord(
                        environment=environment.value,
                        category=item.category.value,
                        symbol=item.symbol,
                        base_coin=item.base_coin,
                        quote_coin=item.quote_coin,
                        status=item.status,
                        tick_size=item.tick_size,
                        quantity_step=item.quantity_step,
                        minimum_order_quantity=item.minimum_order_quantity,
                        minimum_notional=item.minimum_notional,
                        funding_interval_minutes=item.funding_interval_minutes,
                        refreshed_at=refreshed_at,
                    )
                    for item in instruments
                ]
            )
            await session.commit()

    async def list_instruments(self, *, environment: BrokerEnvironment) -> tuple[Instrument, ...]:
        async with self.sessions() as session:
            records = (
                await session.scalars(
                    select(MarketInstrumentRecord)
                    .where(MarketInstrumentRecord.environment == environment.value)
                    .order_by(MarketInstrumentRecord.category, MarketInstrumentRecord.symbol)
                )
            ).all()
        return tuple(self._instrument(record) for record in records)

    async def instrument_refresh_time(self, *, environment: BrokerEnvironment) -> datetime | None:
        async with self.sessions() as session:
            return await session.scalar(
                select(func.max(MarketInstrumentRecord.refreshed_at)).where(
                    MarketInstrumentRecord.environment == environment.value
                )
            )

    async def get_instrument(
        self,
        *,
        environment: BrokerEnvironment,
        category: MarketCategory,
        symbol: str,
    ) -> Instrument | None:
        async with self.sessions() as session:
            record = await session.get(
                MarketInstrumentRecord,
                (environment.value, category.value, symbol),
            )
        return self._instrument(record) if record is not None else None

    async def get_ticker(
        self,
        *,
        environment: BrokerEnvironment,
        category: MarketCategory,
        symbol: str,
    ) -> TickerSnapshot | None:
        async with self.sessions() as session:
            record = await session.get(
                MarketTickerRecord,
                (environment.value, category.value, symbol),
            )
        if record is None:
            return None
        return TickerSnapshot(
            category=MarketCategory(record.category),
            symbol=record.symbol,
            last_price=record.last_price,
            bid_price=record.bid_price,
            ask_price=record.ask_price,
            turnover_24h=record.turnover_24h,
            volume_24h=record.volume_24h,
            price_change_24h=record.price_change_24h,
            open_interest=record.open_interest,
            funding_rate=record.funding_rate,
            next_funding_at=(
                _as_utc(record.next_funding_at) if record.next_funding_at is not None else None
            ),
            observed_at=_as_utc(record.observed_at),
        )

    async def replace_latest_tickers(
        self,
        *,
        environment: BrokerEnvironment,
        snapshots: tuple[TickerSnapshot, ...],
    ) -> None:
        async with self.sessions() as session:
            await session.execute(
                delete(MarketTickerRecord).where(
                    MarketTickerRecord.environment == environment.value
                )
            )
            session.add_all(
                [
                    MarketTickerRecord(
                        environment=environment.value,
                        category=item.category.value,
                        symbol=item.symbol,
                        last_price=item.last_price,
                        bid_price=item.bid_price,
                        ask_price=item.ask_price,
                        turnover_24h=item.turnover_24h,
                        volume_24h=item.volume_24h,
                        price_change_24h=item.price_change_24h,
                        open_interest=item.open_interest,
                        funding_rate=item.funding_rate,
                        next_funding_at=item.next_funding_at,
                        observed_at=item.observed_at,
                    )
                    for item in snapshots
                ]
            )
            await session.commit()

    async def save_scan(self, scan: MarketScan) -> None:
        shortlist = {(item.category, item.symbol) for item in scan.result.agent_shortlist}
        async with self.sessions() as session:
            session.add(
                MarketScanRunRecord(
                    id=scan.id,
                    environment=scan.environment.value,
                    source_count=scan.source_count,
                    hot_count=len(scan.result.hot_universe),
                    shortlist_count=len(scan.result.agent_shortlist),
                    observed_at=scan.observed_at,
                    created_at=scan.created_at,
                )
            )
            # The mapped records intentionally have no ORM relationship, so
            # SQLAlchemy cannot infer the foreign-key insert order. Persist the
            # parent run before adding its candidate rows.
            await session.flush()
            session.add_all(
                [
                    MarketCandidateRecord(
                        scan_id=scan.id,
                        category=item.category.value,
                        symbol=item.symbol,
                        rank=rank,
                        selected_for_agent=(item.category, item.symbol) in shortlist,
                        activity_score=item.activity_score,
                        turnover_24h=item.turnover_24h,
                        price_change_24h=item.price_change_24h,
                        spread_bps=item.spread_bps,
                        observed_at=item.observed_at,
                    )
                    for rank, item in enumerate(scan.result.hot_universe, start=1)
                ]
            )
            await session.commit()

    async def latest_scan(self, *, environment: BrokerEnvironment) -> MarketScan | None:
        async with self.sessions() as session:
            run = await session.scalar(
                select(MarketScanRunRecord)
                .where(MarketScanRunRecord.environment == environment.value)
                .order_by(MarketScanRunRecord.created_at.desc())
                .limit(1)
            )
            if run is None:
                return None
            records = (
                await session.scalars(
                    select(MarketCandidateRecord)
                    .where(MarketCandidateRecord.scan_id == run.id)
                    .order_by(MarketCandidateRecord.rank)
                )
            ).all()
        candidates = tuple(self._candidate(record) for record in records)
        return MarketScan(
            id=run.id,
            environment=BrokerEnvironment(run.environment),
            source_count=run.source_count,
            observed_at=_as_utc(run.observed_at),
            created_at=_as_utc(run.created_at),
            result=MarketScanResult(
                hot_universe=candidates,
                agent_shortlist=tuple(
                    candidate
                    for candidate, record in zip(candidates, records, strict=True)
                    if record.selected_for_agent
                ),
            ),
        )

    async def save_portfolio_review(
        self,
        *,
        user_id: str,
        connection_id,
        scan_id: str,
        category: MarketCategory,
        symbol: str,
        outcome: PortfolioReviewOutcome,
    ) -> None:
        document_id = str(
            uuid5(
                NAMESPACE_URL,
                f"portfolio-review:{user_id}:{connection_id}:{scan_id}:{category}:{symbol}",
            )
        )
        async with self.sessions() as session:
            record = await session.get(DocumentRecord, document_id)
            if record is None:
                session.add(
                    DocumentRecord(
                        id=document_id,
                        kind="portfolio_review",
                        status=outcome.code,
                        account_id=user_id,
                        created_at=outcome.evaluated_at,
                        updated_at=outcome.evaluated_at,
                        payload=outcome.model_dump_json(),
                    )
                )
            else:
                record.status = outcome.code
                record.updated_at = outcome.evaluated_at
                record.payload = outcome.model_dump_json()
            await session.commit()

    async def review_for_account(self, review: MarketReview, *, user_id: str, connection_id):
        candidates = []
        async with self.sessions() as session:
            for candidate in review.candidates:
                document_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"portfolio-review:{user_id}:{connection_id}:{review.scan_id}:"
                        f"{candidate.category}:{candidate.symbol}",
                    )
                )
                record = await session.scalar(
                    select(DocumentRecord).where(
                        DocumentRecord.id == document_id,
                        DocumentRecord.kind == "portfolio_review",
                        DocumentRecord.account_id == user_id,
                    )
                )
                outcome = (
                    PortfolioReviewOutcome.model_validate_json(record.payload) if record else None
                )
                candidates.append(candidate.model_copy(update={"portfolio_review": outcome}))
        return review.model_copy(update={"candidates": tuple(candidates)})

    async def save_review(self, review: MarketReview) -> None:
        async with self.sessions() as session:
            run = await session.get(MarketScanRunRecord, review.scan_id)
            if run is None or run.environment != review.environment.value:
                raise KeyError("market scan not found")
            run.analysis_completed_at = review.analyzed_at
            run.approved_strategy_count = review.approved_strategies
            run.candidates_considered = review.candidates_considered
            run.strategy_matches = review.strategy_matches
            run.signals_found = review.signals_found
            run.analyses_completed = review.analysis_completed
            run.no_trade_decisions = review.no_trade_decisions
            run.proposals_created = review.proposals_created
            run.duplicates_skipped = review.duplicates_skipped
            run.gate_rejections = review.gate_rejections
            run.model_available = review.model_available
            for candidate in review.candidates:
                record = await session.get(
                    MarketCandidateRecord,
                    (review.scan_id, candidate.category.value, candidate.symbol),
                )
                if record is None:
                    raise KeyError("market scan candidate not found")
                record.review_status = candidate.status.value
                record.review_reason = candidate.reason
                record.review_strategy_id = candidate.strategy_id
            await session.commit()

    async def latest_review(self, *, environment: BrokerEnvironment) -> MarketReview | None:
        async with self.sessions() as session:
            run = await session.scalar(
                select(MarketScanRunRecord)
                .where(
                    MarketScanRunRecord.environment == environment.value,
                    MarketScanRunRecord.analysis_completed_at.is_not(None),
                )
                .order_by(MarketScanRunRecord.analysis_completed_at.desc())
                .limit(1)
            )
            if run is None:
                return None
            records = (
                await session.scalars(
                    select(MarketCandidateRecord)
                    .where(
                        MarketCandidateRecord.scan_id == run.id,
                        MarketCandidateRecord.review_status.is_not(None),
                    )
                    .order_by(MarketCandidateRecord.rank)
                    .limit(5)
                )
            ).all()
        return MarketReview(
            scan_id=run.id,
            environment=BrokerEnvironment(run.environment),
            analyzed_at=_as_utc(run.analysis_completed_at),
            approved_strategies=run.approved_strategy_count or 0,
            candidates_considered=run.candidates_considered or 0,
            strategy_matches=run.strategy_matches or 0,
            signals_found=run.signals_found or 0,
            analysis_completed=run.analyses_completed or 0,
            no_trade_decisions=run.no_trade_decisions or 0,
            proposals_created=run.proposals_created or 0,
            duplicates_skipped=run.duplicates_skipped or 0,
            gate_rejections=run.gate_rejections or 0,
            model_available=bool(run.model_available),
            candidates=tuple(
                MarketReviewCandidate(
                    category=MarketCategory(record.category),
                    symbol=record.symbol,
                    rank=record.rank,
                    status=MarketReviewStatus(record.review_status),
                    reason=record.review_reason,
                    strategy_id=record.review_strategy_id,
                )
                for record in records
            ),
        )

    async def request_analysis(
        self,
        *,
        request_id: str,
        user_id: str,
        environment: BrokerEnvironment,
        requested_at: datetime,
    ) -> MarketAnalysisRequest:
        async with self.sessions() as session:
            active = await session.scalar(
                select(MarketAnalysisRequestRecord)
                .where(
                    MarketAnalysisRequestRecord.user_id == user_id,
                    MarketAnalysisRequestRecord.environment == environment.value,
                    MarketAnalysisRequestRecord.status.in_(
                        (
                            MarketAnalysisRequestStatus.QUEUED.value,
                            MarketAnalysisRequestStatus.RUNNING.value,
                        )
                    ),
                )
                .order_by(MarketAnalysisRequestRecord.requested_at.desc())
                .limit(1)
            )
            if active is not None:
                return self._analysis_request(active)
            record = MarketAnalysisRequestRecord(
                id=request_id,
                user_id=user_id,
                environment=environment.value,
                status=MarketAnalysisRequestStatus.QUEUED.value,
                requested_at=requested_at,
            )
            session.add(record)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                active = await session.scalar(
                    select(MarketAnalysisRequestRecord).where(
                        MarketAnalysisRequestRecord.user_id == user_id,
                        MarketAnalysisRequestRecord.environment == environment.value,
                        MarketAnalysisRequestRecord.status.in_(
                            (
                                MarketAnalysisRequestStatus.QUEUED.value,
                                MarketAnalysisRequestStatus.RUNNING.value,
                            )
                        ),
                    )
                )
                if active is None:
                    raise
                return self._analysis_request(active)
            await session.refresh(record)
            return self._analysis_request(record)

    async def analysis_request(
        self,
        *,
        user_id: str,
        request_id: str,
    ) -> MarketAnalysisRequest | None:
        async with self.sessions() as session:
            record = await session.scalar(
                select(MarketAnalysisRequestRecord).where(
                    MarketAnalysisRequestRecord.id == request_id,
                    MarketAnalysisRequestRecord.user_id == user_id,
                )
            )
        return self._analysis_request(record) if record is not None else None

    async def claim_analysis_requests(
        self,
        *,
        environment: BrokerEnvironment,
        started_at: datetime,
        stale_before: datetime,
        limit: int,
    ) -> tuple[MarketAnalysisRequest, ...]:
        async with self.sessions() as session:
            records = (
                await session.scalars(
                    select(MarketAnalysisRequestRecord)
                    .where(
                        MarketAnalysisRequestRecord.environment == environment.value,
                        or_(
                            MarketAnalysisRequestRecord.status
                            == MarketAnalysisRequestStatus.QUEUED.value,
                            and_(
                                MarketAnalysisRequestRecord.status
                                == MarketAnalysisRequestStatus.RUNNING.value,
                                or_(
                                    MarketAnalysisRequestRecord.started_at.is_(None),
                                    MarketAnalysisRequestRecord.started_at <= stale_before,
                                ),
                            ),
                        ),
                    )
                    .order_by(MarketAnalysisRequestRecord.requested_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for record in records:
                record.status = MarketAnalysisRequestStatus.RUNNING.value
                record.started_at = started_at
            await session.commit()
            return tuple(self._analysis_request(record) for record in records)

    async def complete_analysis_requests(
        self,
        *,
        requests: tuple[MarketAnalysisRequest, ...],
        scan_id: str,
        completed_at: datetime,
    ) -> None:
        await self._finish_analysis_requests(
            requests=requests,
            status=MarketAnalysisRequestStatus.COMPLETED,
            completed_at=completed_at,
            scan_id=scan_id,
            error_code=None,
        )

    async def fail_analysis_requests(
        self,
        *,
        requests: tuple[MarketAnalysisRequest, ...],
        error_code: str,
        completed_at: datetime,
    ) -> None:
        await self._finish_analysis_requests(
            requests=requests,
            status=MarketAnalysisRequestStatus.FAILED,
            completed_at=completed_at,
            scan_id=None,
            error_code=error_code,
        )

    async def _finish_analysis_requests(
        self,
        *,
        requests: tuple[MarketAnalysisRequest, ...],
        status: MarketAnalysisRequestStatus,
        completed_at: datetime,
        scan_id: str | None,
        error_code: str | None,
    ) -> None:
        if not requests:
            return
        request_ids = tuple(item.id for item in requests)
        async with self.sessions() as session:
            records = (
                await session.scalars(
                    select(MarketAnalysisRequestRecord)
                    .where(
                        MarketAnalysisRequestRecord.id.in_(request_ids),
                        MarketAnalysisRequestRecord.status
                        == MarketAnalysisRequestStatus.RUNNING.value,
                    )
                    .with_for_update()
                )
            ).all()
            for record in records:
                record.status = status.value
                record.completed_at = completed_at
                record.scan_id = scan_id
                record.error_code = error_code
            await session.commit()

    @staticmethod
    def _instrument(record: MarketInstrumentRecord) -> Instrument:
        return Instrument(
            category=MarketCategory(record.category),
            symbol=record.symbol,
            base_coin=record.base_coin,
            quote_coin=record.quote_coin,
            status=record.status,
            tick_size=record.tick_size,
            quantity_step=record.quantity_step,
            minimum_order_quantity=record.minimum_order_quantity,
            minimum_notional=record.minimum_notional,
            funding_interval_minutes=record.funding_interval_minutes,
        )

    @staticmethod
    def _candidate(record: MarketCandidateRecord) -> MarketCandidate:
        return MarketCandidate(
            category=MarketCategory(record.category),
            symbol=record.symbol,
            activity_score=record.activity_score,
            turnover_24h=record.turnover_24h,
            price_change_24h=record.price_change_24h,
            spread_bps=record.spread_bps,
            observed_at=_as_utc(record.observed_at),
        )

    @staticmethod
    def _analysis_request(record: MarketAnalysisRequestRecord) -> MarketAnalysisRequest:
        return MarketAnalysisRequest(
            id=record.id,
            environment=BrokerEnvironment(record.environment),
            status=MarketAnalysisRequestStatus(record.status),
            requested_at=_as_utc(record.requested_at),
            started_at=_as_utc(record.started_at) if record.started_at is not None else None,
            completed_at=(
                _as_utc(record.completed_at) if record.completed_at is not None else None
            ),
            scan_id=record.scan_id,
            error_code=record.error_code,
        )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
