from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from signalos_backend.domain import utc_now


class BrokerEnvironment(StrEnum):
    MAINNET = "mainnet"
    TESTNET = "testnet"


class BrokerCredentialPurpose(StrEnum):
    BROKER_ACCESS = "broker_access"


class ConnectionStatus(StrEnum):
    PENDING = "pending"
    VERIFYING = "verifying"
    SYNCING = "syncing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    REVOKED = "revoked"


class BrokerProvider(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Literal["bybit"] = "bybit"
    display_name: str = "Bybit"
    status: Literal["enabled", "coming_soon"] = "enabled"
    default_environment: BrokerEnvironment = BrokerEnvironment.MAINNET
    supported_environments: tuple[BrokerEnvironment, ...] = (
        BrokerEnvironment.MAINNET,
        BrokerEnvironment.TESTNET,
    )
    supports_account_read: bool = True
    supports_trading: bool = True


class BrokerCredentialsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    api_key: SecretStr = Field(min_length=8, max_length=256)
    api_secret: SecretStr = Field(min_length=8, max_length=512)


class CreateBrokerConnection(BrokerCredentialsInput):
    provider_id: Literal["bybit"]
    environment: BrokerEnvironment = BrokerEnvironment.MAINNET


class BrokerContextSwitch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: BrokerEnvironment
    connection_id: UUID


class BrokerContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    environment: BrokerEnvironment
    connection_id: UUID
    switched_at: datetime
    invalidated_proposals: int = Field(default=0, ge=0)


class ActiveBrokerAccount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    connection_id: UUID
    environment: BrokerEnvironment


class BrokerConnection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    provider_id: Literal["bybit"]
    environment: BrokerEnvironment
    status: ConnectionStatus
    external_uid: str | None = None
    spot_trading_enabled: bool = False
    derivatives_trading_enabled: bool = False
    credential_purposes: tuple[BrokerCredentialPurpose, ...] = ()
    last_verified_at: datetime | None = None
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BybitKeyInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    parent_uid: str
    is_master: bool
    read_only: bool
    ips: tuple[str, ...] = ()
    permissions: dict[str, tuple[str, ...]] = Field(default_factory=dict)


class AccountBalance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    coin: str = Field(pattern=r"^[A-Z0-9]{2,20}$")
    wallet_balance: Decimal
    equity: Decimal
    available_to_withdraw: Decimal


class AccountSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    account_type: str
    total_equity: Decimal
    available_balance: Decimal
    balances: tuple[AccountBalance, ...]
    captured_at: datetime = Field(default_factory=utc_now)


class PortfolioSummary(AccountSnapshot):
    """Latest reconciled account state for the user's active broker context."""

    connection_id: UUID
    provider_id: Literal["bybit"]
    environment: BrokerEnvironment
    invested_value: Decimal


class BrokerPolicyError(ValueError):
    """A credential or connection violates deterministic broker policy."""


class BrokerProviderError(RuntimeError):
    """The external broker returned an invalid response or could not be reached."""


class BrokerCredentialRejected(BrokerProviderError):
    """Bybit definitively rejected a user-supplied credential."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class BrokerOrderRejected(BrokerProviderError):
    """Bybit definitively rejected an authenticated order request."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
