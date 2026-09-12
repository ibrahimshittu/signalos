from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from signalos_backend.brokers.domain import (
    AccountSnapshot,
    BrokerConnection,
    BrokerCredentialPurpose,
    BrokerEnvironment,
    BrokerPolicyError,
    BrokerProvider,
    BybitKeyInfo,
    CreateBrokerConnection,
    PortfolioSummary,
)
from signalos_backend.brokers.store import BrokerStore
from signalos_backend.config import Settings
from signalos_backend.security.credentials import CredentialCipher


class BybitGateway(Protocol):
    async def get_key_info(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
    ) -> BybitKeyInfo: ...

    async def get_account_snapshot(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
    ) -> AccountSnapshot: ...


@dataclass
class BrokerService:
    settings: Settings
    store: BrokerStore
    cipher: CredentialCipher
    bybit: BybitGateway

    def providers(self) -> tuple[BrokerProvider, ...]:
        return (BrokerProvider(),)

    async def portfolio_summary(self, *, user_id: str) -> PortfolioSummary | None:
        return await self.store.get_portfolio_summary(user_id=user_id)

    async def create(self, *, user_id: str, payload: CreateBrokerConnection) -> BrokerConnection:
        return await self.store.create_connection(
            user_id=user_id,
            provider_id=payload.provider_id,
            environment=payload.environment,
            api_key_ciphertext=self.cipher.encrypt(payload.api_key.get_secret_value()),
            api_secret_ciphertext=self.cipher.encrypt(payload.api_secret.get_secret_value()),
        )

    async def get(self, *, user_id: str, connection_id: UUID) -> BrokerConnection | None:
        return await self.store.get_connection(user_id=user_id, connection_id=connection_id)

    async def verify(self, *, user_id: str, connection_id: UUID) -> BrokerConnection:
        connection = await self._require_connection(user_id=user_id, connection_id=connection_id)
        await self.store.mark_verifying(user_id=user_id, connection_id=connection_id)
        api_key, api_secret = await self._read_credentials(
            user_id=user_id,
            connection_id=connection_id,
            purpose=BrokerCredentialPurpose.BROKER_ACCESS,
        )
        try:
            key_info = await self.bybit.get_key_info(
                api_key=api_key,
                api_secret=api_secret,
                environment=connection.environment,
            )
            self._validate_connected_key(key_info, connection.environment)
        except Exception as exc:
            await self.store.mark_failed(
                user_id=user_id,
                connection_id=connection_id,
                error_code=type(exc).__name__,
            )
            raise
        fingerprint = self._permission_fingerprint(key_info)
        spot_trading_enabled, derivatives_trading_enabled = self._trading_capabilities(key_info)
        return await self.store.mark_verified(
            user_id=user_id,
            connection_id=connection_id,
            external_uid=key_info.user_id,
            parent_uid=key_info.parent_uid,
            permission_fingerprint=fingerprint,
            spot_trading_enabled=spot_trading_enabled,
            derivatives_trading_enabled=derivatives_trading_enabled,
        )

    async def sync(self, *, user_id: str, connection_id: UUID) -> BrokerConnection:
        connection = await self._require_connection(user_id=user_id, connection_id=connection_id)
        if connection.status.value not in {"syncing", "healthy", "degraded"}:
            raise BrokerPolicyError("Bybit connection must be verified before account sync")
        api_key, api_secret = await self._read_credentials(
            user_id=user_id,
            connection_id=connection_id,
            purpose=BrokerCredentialPurpose.BROKER_ACCESS,
        )
        snapshot = await self.bybit.get_account_snapshot(
            api_key=api_key,
            api_secret=api_secret,
            environment=connection.environment,
        )
        return await self.store.save_snapshot(
            user_id=user_id, connection_id=connection_id, snapshot=snapshot
        )

    async def _require_connection(self, *, user_id: str, connection_id: UUID) -> BrokerConnection:
        connection = await self.get(user_id=user_id, connection_id=connection_id)
        if connection is None:
            raise KeyError(connection_id)
        return connection

    async def _read_credentials(
        self,
        *,
        user_id: str,
        connection_id: UUID,
        purpose: BrokerCredentialPurpose,
    ) -> tuple[str, str]:
        values = await self.store.get_credential_ciphertexts(
            user_id=user_id, connection_id=connection_id, purpose=purpose
        )
        if values is None:
            raise BrokerPolicyError(f"missing {purpose.value} credentials")
        return self.cipher.decrypt(values[0]), self.cipher.decrypt(values[1])

    def _validate_connected_key(
        self, key_info: BybitKeyInfo, environment: BrokerEnvironment
    ) -> None:
        if key_info.read_only:
            raise BrokerPolicyError("SignalOS requires a read-write Bybit API key")
        forbidden = sorted(
            {
                permission
                for permission in key_info.permissions.get("Wallet", ())
                if permission
                in {"AccountTransfer", "SubMemberTransfer", "SubMemberTransferList", "Withdraw"}
            }
        )
        if forbidden:
            raise BrokerPolicyError(
                f"Bybit key has forbidden wallet permissions: {', '.join(forbidden)}"
            )
        contract_permissions = key_info.permissions.get("ContractTrade", ())
        can_trade_contracts = "Order" in contract_permissions and "Position" in contract_permissions
        can_trade_spot = "SpotTrade" in key_info.permissions.get("Spot", ())
        if not can_trade_contracts and not can_trade_spot:
            raise BrokerPolicyError("Bybit key must include spot or contract order permission")
        if (
            self.settings.environment == "production"
            and environment is BrokerEnvironment.MAINNET
            and not key_info.ips
        ):
            raise BrokerPolicyError("Production mainnet Bybit keys must be IP restricted")

    @staticmethod
    def _trading_capabilities(key_info: BybitKeyInfo) -> tuple[bool, bool]:
        return (
            "SpotTrade" in key_info.permissions.get("Spot", ()),
            "Order" in key_info.permissions.get("ContractTrade", ())
            and "Position" in key_info.permissions.get("ContractTrade", ()),
        )

    @staticmethod
    def _permission_fingerprint(key_info: BybitKeyInfo) -> str:
        return hashlib.sha256(
            json.dumps(
                {
                    "read_only": key_info.read_only,
                    "ips": sorted(key_info.ips),
                    "permissions": {
                        key: sorted(value) for key, value in sorted(key_info.permissions.items())
                    },
                },
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
