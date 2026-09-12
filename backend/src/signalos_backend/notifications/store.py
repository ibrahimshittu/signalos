from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from signalos_backend.db import Base
from signalos_backend.notifications.domain import (
    DeliveryStatus,
    DevicePlatform,
    PushDevice,
    PushDeviceStatus,
)


class PushDeviceRecord(Base):
    __tablename__ = "push_devices"

    installation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    platform: Mapped[str] = mapped_column(String(20))
    expo_project_id: Mapped[str] = mapped_column(String(36), index=True)
    token_ciphertext: Mapped[str] = mapped_column(Text)
    token_fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class NotificationDeliveryRecord(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("proposal_id", "installation_id", "event_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), index=True)
    proposal_id: Mapped[str] = mapped_column(
        ForeignKey("trade_proposals.id", ondelete="CASCADE"), index=True
    )
    installation_id: Mapped[str] = mapped_column(
        ForeignKey("push_devices.installation_id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    expo_ticket_id: Mapped[str | None] = mapped_column(String(100), index=True)
    error_code: Mapped[str | None] = mapped_column(String(100))
    attempt_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


@dataclass(frozen=True)
class RegisteredDevice:
    installation_id: UUID
    user_id: str
    token_ciphertext: str


@dataclass(frozen=True)
class PendingDelivery:
    id: UUID
    installation_id: UUID
    token_ciphertext: str


@dataclass(frozen=True)
class TicketedDelivery:
    id: UUID
    installation_id: UUID
    expo_ticket_id: str


class NotificationStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def register_device(
        self,
        *,
        user_id: str,
        installation_id: UUID,
        platform: DevicePlatform,
        expo_project_id: UUID,
        token_ciphertext: str,
        token_fingerprint: str,
        now: datetime,
    ) -> PushDevice:
        async with self.sessions() as session:
            record = await session.get(PushDeviceRecord, str(installation_id), with_for_update=True)
            token_record = await session.scalar(
                select(PushDeviceRecord)
                .where(PushDeviceRecord.token_fingerprint == token_fingerprint)
                .with_for_update()
            )
            if record is not None and record.user_id != user_id:
                raise PermissionError("notification installation belongs to another user")
            if token_record is not None and token_record.user_id != user_id:
                raise PermissionError("notification token belongs to another user")
            if token_record is not None and token_record.installation_id != str(installation_id):
                await session.delete(token_record)
                await session.flush()
            if record is None:
                record = PushDeviceRecord(
                    installation_id=str(installation_id),
                    user_id=user_id,
                    platform=platform.value,
                    expo_project_id=str(expo_project_id),
                    token_ciphertext=token_ciphertext,
                    token_fingerprint=token_fingerprint,
                    status=PushDeviceStatus.ACTIVE.value,
                    last_error_code=None,
                    last_registered_at=now,
                    created_at=now,
                    updated_at=now,
                )
                session.add(record)
            else:
                record.platform = platform.value
                record.expo_project_id = str(expo_project_id)
                record.token_ciphertext = token_ciphertext
                record.token_fingerprint = token_fingerprint
                record.status = PushDeviceStatus.ACTIVE.value
                record.last_error_code = None
                record.last_registered_at = now
                record.updated_at = now
            await session.commit()
            return self._device(record)

    async def list_devices(self, *, user_id: str) -> tuple[PushDevice, ...]:
        async with self.sessions() as session:
            records = (
                await session.scalars(
                    select(PushDeviceRecord)
                    .where(PushDeviceRecord.user_id == user_id)
                    .order_by(PushDeviceRecord.updated_at.desc())
                )
            ).all()
            return tuple(self._device(record) for record in records)

    async def remove_device(self, *, user_id: str, installation_id: UUID) -> bool:
        async with self.sessions() as session:
            record = await session.get(PushDeviceRecord, str(installation_id), with_for_update=True)
            if record is None or record.user_id != user_id:
                return False
            await session.delete(record)
            await session.commit()
            return True

    async def prepare_deliveries(
        self, *, user_id: str, proposal_id: UUID, now: datetime
    ) -> tuple[PendingDelivery, ...]:
        async with self.sessions() as session:
            devices = (
                await session.scalars(
                    select(PushDeviceRecord).where(
                        PushDeviceRecord.user_id == user_id,
                        PushDeviceRecord.status == PushDeviceStatus.ACTIVE.value,
                    )
                )
            ).all()
            pending: list[PendingDelivery] = []
            for device in devices:
                existing = await session.scalar(
                    select(NotificationDeliveryRecord).where(
                        NotificationDeliveryRecord.proposal_id == str(proposal_id),
                        NotificationDeliveryRecord.installation_id == device.installation_id,
                        NotificationDeliveryRecord.event_type == "proposal_available",
                    )
                )
                if existing is None:
                    existing = NotificationDeliveryRecord(
                        id=str(uuid4()),
                        user_id=user_id,
                        proposal_id=str(proposal_id),
                        installation_id=device.installation_id,
                        event_type="proposal_available",
                        status=DeliveryStatus.PENDING.value,
                        expo_ticket_id=None,
                        error_code=None,
                        attempt_count=0,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(existing)
                    await session.flush()
                if (
                    existing.status
                    in {
                        DeliveryStatus.PENDING.value,
                        DeliveryStatus.FAILED.value,
                    }
                    and existing.attempt_count < 5
                ):
                    pending.append(
                        PendingDelivery(
                            id=UUID(existing.id),
                            installation_id=UUID(device.installation_id),
                            token_ciphertext=device.token_ciphertext,
                        )
                    )
            await session.commit()
            return tuple(pending)

    async def mark_ticket(
        self,
        *,
        delivery_id: UUID,
        ticket_id: str | None,
        error_code: str | None,
        now: datetime,
    ) -> None:
        async with self.sessions() as session:
            record = await session.get(NotificationDeliveryRecord, str(delivery_id))
            if record is None:
                raise KeyError(delivery_id)
            record.attempt_count += 1
            record.updated_at = now
            record.expo_ticket_id = ticket_id
            record.error_code = error_code
            record.status = (
                DeliveryStatus.TICKETED.value if ticket_id else DeliveryStatus.FAILED.value
            )
            if error_code == "DeviceNotRegistered":
                device = await session.get(PushDeviceRecord, record.installation_id)
                if device is not None:
                    device.status = PushDeviceStatus.DISABLED.value
                    device.last_error_code = error_code
                    device.updated_at = now
            await session.commit()

    async def failed_proposals(self, *, limit: int = 100) -> tuple[tuple[str, UUID], ...]:
        async with self.sessions() as session:
            rows = (
                await session.execute(
                    select(
                        NotificationDeliveryRecord.user_id,
                        NotificationDeliveryRecord.proposal_id,
                    )
                    .where(
                        NotificationDeliveryRecord.status == DeliveryStatus.FAILED.value,
                        NotificationDeliveryRecord.attempt_count < 5,
                    )
                    .distinct()
                    .limit(limit)
                )
            ).all()
            return tuple((user_id, UUID(proposal_id)) for user_id, proposal_id in rows)

    async def ticketed_deliveries(self, *, limit: int = 1_000) -> tuple[TicketedDelivery, ...]:
        async with self.sessions() as session:
            records = (
                await session.scalars(
                    select(NotificationDeliveryRecord)
                    .where(
                        NotificationDeliveryRecord.status == DeliveryStatus.TICKETED.value,
                        NotificationDeliveryRecord.expo_ticket_id.is_not(None),
                    )
                    .order_by(NotificationDeliveryRecord.updated_at)
                    .limit(limit)
                )
            ).all()
            return tuple(
                TicketedDelivery(
                    id=UUID(record.id),
                    installation_id=UUID(record.installation_id),
                    expo_ticket_id=record.expo_ticket_id or "",
                )
                for record in records
            )

    async def mark_receipt(
        self,
        *,
        delivery_id: UUID,
        delivered: bool,
        error_code: str | None,
        disable_device: bool,
        now: datetime,
    ) -> None:
        async with self.sessions() as session:
            record = await session.get(NotificationDeliveryRecord, str(delivery_id))
            if record is None:
                raise KeyError(delivery_id)
            record.status = (
                DeliveryStatus.DELIVERED.value if delivered else DeliveryStatus.FAILED.value
            )
            record.error_code = error_code
            record.updated_at = now
            if disable_device:
                device = await session.get(PushDeviceRecord, record.installation_id)
                if device is not None:
                    device.status = PushDeviceStatus.DISABLED.value
                    device.last_error_code = error_code
                    device.updated_at = now
            await session.commit()

    @staticmethod
    def _device(record: PushDeviceRecord) -> PushDevice:
        return PushDevice(
            installation_id=UUID(record.installation_id),
            platform=record.platform,
            expo_project_id=UUID(record.expo_project_id),
            status=record.status,
            last_registered_at=NotificationStore._as_utc(record.last_registered_at),
            created_at=NotificationStore._as_utc(record.created_at),
            updated_at=NotificationStore._as_utc(record.updated_at),
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
