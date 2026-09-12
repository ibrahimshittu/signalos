from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from signalos_backend.brokers.domain import (
    AccountBalance,
    AccountSnapshot,
    ActiveBrokerAccount,
    BrokerConnection,
    BrokerContext,
    BrokerCredentialPurpose,
    BrokerEnvironment,
    ConnectionStatus,
    PortfolioSummary,
)
from signalos_backend.db import Base


class BrokerConnectionRecord(Base):
    __tablename__ = "broker_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    provider_id: Mapped[str] = mapped_column(String(40), index=True)
    environment: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    external_uid: Mapped[str | None] = mapped_column(String(100), index=True)
    parent_uid: Mapped[str | None] = mapped_column(String(100))
    permission_fingerprint: Mapped[str | None] = mapped_column(String(64))
    spot_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    derivatives_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BrokerCredentialRecord(Base):
    __tablename__ = "broker_credentials"
    __table_args__ = (UniqueConstraint("connection_id", "purpose"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="CASCADE"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(30))
    api_key_ciphertext: Mapped[str] = mapped_column(Text)
    api_secret_ciphertext: Mapped[str] = mapped_column(Text)
    external_uid: Mapped[str | None] = mapped_column(String(100))
    permission_fingerprint: Mapped[str | None] = mapped_column(String(64))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AccountSnapshotRecord(Base):
    __tablename__ = "account_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="CASCADE"), index=True
    )
    account_type: Mapped[str] = mapped_column(String(40))
    total_equity: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    available_balance: Mapped[Decimal] = mapped_column(Numeric(30, 12))
    balances: Mapped[list[dict[str, str]]] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BrokerContextRecord(Base):
    __tablename__ = "broker_contexts"

    user_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    environment: Mapped[str] = mapped_column(String(20), index=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="RESTRICT"), unique=True, index=True
    )
    switched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BrokerStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def create_connection(
        self,
        *,
        user_id: str,
        provider_id: str,
        environment: BrokerEnvironment,
        api_key_ciphertext: str,
        api_secret_ciphertext: str,
    ) -> BrokerConnection:
        now = datetime.now(UTC)
        connection_id = uuid4()
        async with self.sessions() as session:
            session.add(
                BrokerConnectionRecord(
                    id=str(connection_id),
                    user_id=user_id,
                    provider_id=provider_id,
                    environment=environment.value,
                    status=ConnectionStatus.PENDING.value,
                    external_uid=None,
                    parent_uid=None,
                    permission_fingerprint=None,
                    spot_trading_enabled=False,
                    derivatives_trading_enabled=False,
                    last_error_code=None,
                    last_verified_at=None,
                    last_synced_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                BrokerCredentialRecord(
                    id=str(uuid4()),
                    connection_id=str(connection_id),
                    purpose=BrokerCredentialPurpose.BROKER_ACCESS.value,
                    api_key_ciphertext=api_key_ciphertext,
                    api_secret_ciphertext=api_secret_ciphertext,
                    external_uid=None,
                    permission_fingerprint=None,
                    verified_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
        result = await self.get_connection(user_id=user_id, connection_id=connection_id)
        if result is None:  # pragma: no cover - database contract violation
            raise RuntimeError("created broker connection could not be loaded")
        return result

    async def get_connection(self, *, user_id: str, connection_id: UUID) -> BrokerConnection | None:
        async with self.sessions() as session:
            record = await session.scalar(
                select(BrokerConnectionRecord).where(
                    BrokerConnectionRecord.id == str(connection_id),
                    BrokerConnectionRecord.user_id == user_id,
                )
            )
            if record is None:
                return None
            purposes = await self._purposes(session, record.id)
            return self._to_domain(record, purposes)

    async def get_credential_ciphertexts(
        self,
        *,
        user_id: str,
        connection_id: UUID,
        purpose: BrokerCredentialPurpose,
    ) -> tuple[str, str] | None:
        async with self.sessions() as session:
            statement = (
                select(BrokerCredentialRecord)
                .join(
                    BrokerConnectionRecord,
                    BrokerConnectionRecord.id == BrokerCredentialRecord.connection_id,
                )
                .where(
                    BrokerConnectionRecord.user_id == user_id,
                    BrokerConnectionRecord.id == str(connection_id),
                    BrokerCredentialRecord.purpose == purpose.value,
                )
            )
            credential = await session.scalar(statement)
            if credential is None:
                return None
            return credential.api_key_ciphertext, credential.api_secret_ciphertext

    async def mark_verifying(self, *, user_id: str, connection_id: UUID) -> None:
        await self._update_connection(
            user_id=user_id,
            connection_id=connection_id,
            status=ConnectionStatus.VERIFYING,
        )

    async def mark_verified(
        self,
        *,
        user_id: str,
        connection_id: UUID,
        external_uid: str,
        parent_uid: str,
        permission_fingerprint: str,
        spot_trading_enabled: bool,
        derivatives_trading_enabled: bool,
    ) -> BrokerConnection:
        now = datetime.now(UTC)
        await self._update_connection(
            user_id=user_id,
            connection_id=connection_id,
            status=ConnectionStatus.SYNCING,
            external_uid=external_uid,
            parent_uid=parent_uid,
            permission_fingerprint=permission_fingerprint,
            spot_trading_enabled=spot_trading_enabled,
            derivatives_trading_enabled=derivatives_trading_enabled,
            last_verified_at=now,
            last_error_code=None,
        )
        async with self.sessions() as session:
            credential = await session.scalar(
                select(BrokerCredentialRecord).where(
                    BrokerCredentialRecord.connection_id == str(connection_id),
                    BrokerCredentialRecord.purpose == BrokerCredentialPurpose.BROKER_ACCESS.value,
                )
            )
            if credential is None:
                raise RuntimeError("broker credential disappeared during verification")
            credential.external_uid = external_uid
            credential.permission_fingerprint = permission_fingerprint
            credential.verified_at = now
            credential.updated_at = now
            await session.commit()
        result = await self.get_connection(user_id=user_id, connection_id=connection_id)
        if result is None:  # pragma: no cover
            raise RuntimeError("verified broker connection could not be loaded")
        return result

    async def mark_failed(self, *, user_id: str, connection_id: UUID, error_code: str) -> None:
        await self._update_connection(
            user_id=user_id,
            connection_id=connection_id,
            status=ConnectionStatus.FAILED,
            last_error_code=error_code[:80],
        )

    async def save_snapshot(
        self, *, user_id: str, connection_id: UUID, snapshot: AccountSnapshot
    ) -> BrokerConnection:
        connection = await self.get_connection(user_id=user_id, connection_id=connection_id)
        if connection is None:
            raise KeyError(connection_id)
        async with self.sessions() as session:
            session.add(
                AccountSnapshotRecord(
                    id=str(uuid4()),
                    connection_id=str(connection_id),
                    account_type=snapshot.account_type,
                    total_equity=snapshot.total_equity,
                    available_balance=snapshot.available_balance,
                    balances=[
                        {
                            "coin": balance.coin,
                            "wallet_balance": str(balance.wallet_balance),
                            "equity": str(balance.equity),
                            "available_to_withdraw": str(balance.available_to_withdraw),
                        }
                        for balance in snapshot.balances
                    ],
                    captured_at=snapshot.captured_at,
                )
            )
            record = await session.get(BrokerConnectionRecord, str(connection_id))
            if record is None or record.user_id != user_id:
                raise KeyError(connection_id)
            record.status = ConnectionStatus.HEALTHY.value
            record.last_synced_at = snapshot.captured_at
            record.updated_at = datetime.now(UTC)
            context = await session.get(BrokerContextRecord, user_id)
            if context is None:
                session.add(
                    BrokerContextRecord(
                        user_id=user_id,
                        environment=record.environment,
                        connection_id=record.id,
                        switched_at=datetime.now(UTC),
                    )
                )
            await session.commit()
        result = await self.get_connection(user_id=user_id, connection_id=connection_id)
        if result is None:  # pragma: no cover
            raise RuntimeError("synced broker connection could not be loaded")
        return result

    async def has_healthy_read_connection(self, user_id: str) -> bool:
        async with self.sessions() as session:
            statement = (
                select(BrokerConnectionRecord.id)
                .join(
                    BrokerContextRecord,
                    BrokerContextRecord.connection_id == BrokerConnectionRecord.id,
                )
                .join(
                    BrokerCredentialRecord,
                    BrokerCredentialRecord.connection_id == BrokerConnectionRecord.id,
                )
                .where(
                    BrokerConnectionRecord.user_id == user_id,
                    BrokerContextRecord.user_id == user_id,
                    BrokerConnectionRecord.provider_id == "bybit",
                    BrokerConnectionRecord.status == ConnectionStatus.HEALTHY.value,
                    BrokerCredentialRecord.purpose == BrokerCredentialPurpose.BROKER_ACCESS.value,
                )
                .limit(1)
            )
            return await session.scalar(statement) is not None

    async def get_context(self, *, user_id: str) -> BrokerContext | None:
        async with self.sessions() as session:
            record = await session.get(BrokerContextRecord, user_id)
            if record is None:
                return None
            switched_at = record.switched_at
            if switched_at.tzinfo is None:
                switched_at = switched_at.replace(tzinfo=UTC)
            return BrokerContext(
                user_id=user_id,
                environment=BrokerEnvironment(record.environment),
                connection_id=UUID(record.connection_id),
                switched_at=switched_at,
            )

    async def list_active_accounts(
        self, *, environment: BrokerEnvironment
    ) -> tuple[ActiveBrokerAccount, ...]:
        """Return healthy, explicitly active accounts for background personalization."""

        async with self.sessions() as session:
            records = (
                await session.execute(
                    select(BrokerContextRecord, BrokerConnectionRecord)
                    .join(
                        BrokerConnectionRecord,
                        BrokerConnectionRecord.id == BrokerContextRecord.connection_id,
                    )
                    .where(
                        BrokerContextRecord.environment == environment.value,
                        BrokerConnectionRecord.environment == environment.value,
                        BrokerConnectionRecord.status == ConnectionStatus.HEALTHY.value,
                    )
                    .order_by(BrokerContextRecord.user_id)
                )
            ).all()
        return tuple(
            ActiveBrokerAccount(
                user_id=context.user_id,
                connection_id=UUID(connection.id),
                environment=environment,
            )
            for context, connection in records
        )

    async def get_portfolio_summary(self, *, user_id: str) -> PortfolioSummary | None:
        """Return only the newest snapshot in the user's active broker context."""

        async with self.sessions() as session:
            statement = (
                select(BrokerConnectionRecord, AccountSnapshotRecord)
                .join(
                    BrokerContextRecord,
                    BrokerContextRecord.connection_id == BrokerConnectionRecord.id,
                )
                .join(
                    AccountSnapshotRecord,
                    AccountSnapshotRecord.connection_id == BrokerConnectionRecord.id,
                )
                .where(
                    BrokerContextRecord.user_id == user_id,
                    BrokerConnectionRecord.user_id == user_id,
                    BrokerConnectionRecord.status == ConnectionStatus.HEALTHY.value,
                )
                .order_by(AccountSnapshotRecord.captured_at.desc())
                .limit(1)
            )
            row = (await session.execute(statement)).first()
            if row is None:
                return None
            connection, snapshot = row
            captured_at = snapshot.captured_at
            if captured_at.tzinfo is None:
                captured_at = captured_at.replace(tzinfo=UTC)
            invested_value = max(snapshot.total_equity - snapshot.available_balance, Decimal("0"))
            return PortfolioSummary(
                connection_id=UUID(connection.id),
                provider_id=connection.provider_id,
                environment=connection.environment,
                account_type=snapshot.account_type,
                total_equity=snapshot.total_equity,
                available_balance=snapshot.available_balance,
                invested_value=invested_value,
                balances=tuple(AccountBalance.model_validate(item) for item in snapshot.balances),
                captured_at=captured_at,
            )

    async def _update_connection(
        self,
        *,
        user_id: str,
        connection_id: UUID,
        status: ConnectionStatus,
        **values: object,
    ) -> None:
        async with self.sessions() as session:
            record = await session.get(BrokerConnectionRecord, str(connection_id))
            if record is None or record.user_id != user_id:
                raise KeyError(connection_id)
            record.status = status.value
            record.updated_at = datetime.now(UTC)
            for field, value in values.items():
                setattr(record, field, value)
            await session.commit()

    @staticmethod
    async def _purposes(
        session: AsyncSession, connection_id: str
    ) -> tuple[BrokerCredentialPurpose, ...]:
        values = (
            await session.scalars(
                select(BrokerCredentialRecord.purpose).where(
                    BrokerCredentialRecord.connection_id == connection_id
                )
            )
        ).all()
        return tuple(BrokerCredentialPurpose(value) for value in values)

    @staticmethod
    def _to_domain(
        record: BrokerConnectionRecord,
        purposes: tuple[BrokerCredentialPurpose, ...],
    ) -> BrokerConnection:
        return BrokerConnection(
            id=UUID(record.id),
            provider_id=record.provider_id,
            environment=record.environment,
            status=record.status,
            external_uid=record.external_uid,
            spot_trading_enabled=record.spot_trading_enabled,
            derivatives_trading_enabled=record.derivatives_trading_enabled,
            credential_purposes=purposes,
            last_verified_at=record.last_verified_at,
            last_synced_at=record.last_synced_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
