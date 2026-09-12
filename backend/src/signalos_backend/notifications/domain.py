from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class DevicePlatform(StrEnum):
    IOS = "ios"
    ANDROID = "android"


class PushDeviceStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    TICKETED = "ticketed"
    DELIVERED = "delivered"
    FAILED = "failed"


class RegisterPushDevice(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    platform: DevicePlatform
    expo_push_token: SecretStr = Field(min_length=20, max_length=256)
    expo_project_id: UUID

    @field_validator("expo_push_token")
    @classmethod
    def validate_expo_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value()
        prefixes = ("ExpoPushToken[", "ExponentPushToken[")
        if not token.startswith(prefixes) or not token.endswith("]"):
            raise ValueError("invalid Expo push token")
        return value


class PushDevice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    installation_id: UUID
    platform: DevicePlatform
    expo_project_id: UUID
    status: PushDeviceStatus
    last_registered_at: datetime
    created_at: datetime
    updated_at: datetime


class ExpoPushMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    to: str
    title: str = Field(max_length=100)
    body: str = Field(max_length=200)
    data: dict[str, str]
    sound: str = "default"
    priority: str = "high"


class ExpoPushTicket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    id: str | None = None
    message: str | None = None
    details: dict[str, str] = Field(default_factory=dict)


class ExpoPushReceipt(ExpoPushTicket):
    pass
