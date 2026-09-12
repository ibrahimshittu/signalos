from __future__ import annotations

import base64
from decimal import Decimal

from fastapi.testclient import TestClient

from signalos_backend.brokers.domain import (
    AccountBalance,
    AccountSnapshot,
    BrokerCredentialRejected,
    BrokerEnvironment,
    BybitKeyInfo,
)
from signalos_backend.config import Settings
from signalos_backend.main import create_app

USER_HEADERS = {"X-SignalOS-User-Id": "user-a"}
OTHER_USER_HEADERS = {"X-SignalOS-User-Id": "user-b"}


class FakeBybitGateway:
    def __init__(
        self,
        *,
        permissions: dict[str, tuple[str, ...]] | None = None,
        read_only: bool = False,
    ) -> None:
        self.permissions = permissions or {
            "ContractTrade": ("Order", "Position"),
            "Spot": ("SpotTrade",),
            "Wallet": (),
        }
        self.read_only = read_only

    async def get_key_info(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
    ) -> BybitKeyInfo:
        assert api_key == "read-key"
        assert api_secret == "read-secret-value"
        assert environment is BrokerEnvironment.MAINNET
        return BybitKeyInfo(
            user_id="123456",
            parent_uid="0",
            is_master=True,
            read_only=self.read_only,
            ips=("203.0.113.10",),
            permissions=self.permissions,
        )

    async def get_account_snapshot(
        self,
        *,
        api_key: str,
        api_secret: str,
        environment: BrokerEnvironment,
    ) -> AccountSnapshot:
        assert api_key == "read-key"
        assert api_secret == "read-secret-value"
        assert environment is BrokerEnvironment.MAINNET
        return AccountSnapshot(
            account_type="UNIFIED",
            total_equity=Decimal("12000.50"),
            available_balance=Decimal("8000.25"),
            balances=(
                AccountBalance(
                    coin="USDT",
                    wallet_balance=Decimal("9000"),
                    equity=Decimal("9000"),
                    available_to_withdraw=Decimal("8000.25"),
                ),
            ),
        )


def make_settings(tmp_path) -> Settings:
    encryption_key = base64.urlsafe_b64encode(b"signalos-test-key-material-00000").decode()
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'studio.db'}",
        api_key="operator",
        credential_encryption_key=encryption_key,
        logfire_send=False,
    )


def profile_payload() -> dict[str, object]:
    return {
        "goals": ["capital_growth"],
        "time_horizon": "swing",
        "liquidity_need": "moderate",
        "investing_experience": "intermediate",
        "trading_experience": "beginner",
        "products_traded": ["stocks_etfs", "crypto_spot"],
        "decision_frequency": "monthly",
        "drawdown_response": "hold",
        "holding_periods": ["intraday", "multi_day"],
        "explanation_detail": "detailed",
        "notification_frequency": "opportunities_only",
        "disclosures_accepted": True,
    }


def test_profile_then_bybit_sync_unlocks_studio(tmp_path):
    app = create_app(make_settings(tmp_path))
    app.state.studio.brokers.bybit = FakeBybitGateway()

    with TestClient(app) as client:
        providers = client.get("/v1/broker-providers", headers=USER_HEADERS)
        assert providers.status_code == 200
        assert providers.json() == [
            {
                "id": "bybit",
                "display_name": "Bybit",
                "status": "enabled",
                "default_environment": "mainnet",
                "supported_environments": ["mainnet", "testnet"],
                "supports_account_read": True,
                "supports_trading": True,
            }
        ]

        initial = client.get("/v1/me/onboarding-state", headers=USER_HEADERS).json()
        assert initial["studio_unlocked"] is False
        assert initial["missing_requirements"] == [
            "investment_profile",
            "disclosures",
            "broker_account_read_connection",
            "initial_account_sync",
        ]

        saved_profile = client.put(
            "/v1/me/investment-profile",
            headers=USER_HEADERS,
            json=profile_payload(),
        )
        assert saved_profile.status_code == 200
        assert saved_profile.json()["user_id"] == "user-a"
        assert saved_profile.json()["intended_capital"] is None
        assert saved_profile.json()["adaptive_mandate"] == {
            "risk_posture": "measured",
            "max_loss_per_trade_pct": "0.0075",
            "max_portfolio_drawdown_pct": "0.08",
            "max_leverage": "1",
            "derivatives_eligible": False,
            "reasons": ["balanced_suitability_inputs", "spot_first"],
            "policy_version": "adaptive-mandate-2.0.0",
        }

        personalization = client.get("/v1/me/personalization", headers=USER_HEADERS)
        assert personalization.status_code == 200
        assert personalization.json()["source"] == "deterministic_fallback"
        assert personalization.json()["preferences"]["preferred_markets"] == ["spot"]
        assert personalization.json()["safety_mandate"]["max_leverage"] == "1"

        edited = client.put(
            "/v1/me/personalization",
            headers=USER_HEADERS,
            json={
                "preferred_sessions": ["london", "new_york"],
                "notification_frequency": "daily_digest",
            },
        )
        assert edited.status_code == 200
        assert edited.json()["source"] == "user_edited"
        assert edited.json()["preferences"]["preferred_sessions"] == [
            "london",
            "new_york",
        ]
        assert edited.json()["safety_mandate"]["max_leverage"] == "1"

        regenerated = client.post(
            "/v1/me/personalization/generate", headers=USER_HEADERS
        )
        assert regenerated.status_code == 200
        assert regenerated.json()["source"] == "deterministic_fallback"

        created = client.post(
            "/v1/broker-connections",
            headers=USER_HEADERS,
            json={
                "provider_id": "bybit",
                "environment": "mainnet",
                "api_key": "read-key",
                "api_secret": "read-secret-value",
            },
        )
        assert created.status_code == 201
        connection = created.json()
        assert connection["environment"] == "mainnet"
        assert connection["status"] == "pending"
        assert "api_key" not in connection
        assert "api_secret" not in connection

        isolated = client.get(
            f"/v1/broker-connections/{connection['id']}", headers=OTHER_USER_HEADERS
        )
        assert isolated.status_code == 404

        verified = client.post(
            f"/v1/broker-connections/{connection['id']}/verify", headers=USER_HEADERS
        )
        assert verified.status_code == 200
        assert verified.json()["status"] == "syncing"
        assert verified.json()["external_uid"] == "123456"
        assert verified.json()["credential_purposes"] == ["broker_access"]
        assert verified.json()["spot_trading_enabled"] is True
        assert verified.json()["derivatives_trading_enabled"] is True

        synced = client.post(
            f"/v1/broker-connections/{connection['id']}/sync", headers=USER_HEADERS
        )
        assert synced.status_code == 200
        assert synced.json()["status"] == "healthy"
        assert synced.json()["last_synced_at"] is not None

        portfolio = client.get("/v1/portfolio-summary", headers=USER_HEADERS)
        assert portfolio.status_code == 200
        portfolio_payload = portfolio.json()
        captured_at = portfolio_payload.pop("captured_at")
        assert captured_at.removesuffix("Z") == synced.json()["last_synced_at"]
        assert portfolio_payload == {
            "connection_id": connection["id"],
            "provider_id": "bybit",
            "environment": "mainnet",
            "account_type": "UNIFIED",
            "total_equity": "12000.500000000000",
            "available_balance": "8000.250000000000",
            "invested_value": "4000.250000000000",
            "balances": [
                {
                    "coin": "USDT",
                    "wallet_balance": "9000",
                    "equity": "9000",
                    "available_to_withdraw": "8000.25",
                }
            ],
        }
        assert client.get("/v1/portfolio-summary", headers=OTHER_USER_HEADERS).status_code == 404

        completed = client.get("/v1/me/onboarding-state", headers=USER_HEADERS).json()
        assert completed["studio_unlocked"] is True
        assert completed["missing_requirements"] == []
        assert completed["investment_profile"]["user_id"] == "user-a"
        assert completed["broker_connection"]["id"] == connection["id"]
        other = client.get("/v1/me/onboarding-state", headers=OTHER_USER_HEADERS).json()
        assert other["investment_profile"] is None
        assert other["broker_connection"] is None

    database_bytes = (tmp_path / "studio.db").read_bytes()
    assert b"read-secret-value" not in database_bytes
    assert b"read-key" not in database_bytes


def test_connection_rejects_dangerous_wallet_permissions(tmp_path):
    app = create_app(make_settings(tmp_path))
    app.state.studio.brokers.bybit = FakeBybitGateway(
        permissions={"ContractTrade": ("Position",), "Wallet": ("Withdraw",)}
    )

    with TestClient(app) as client:
        client.put("/v1/me/investment-profile", headers=USER_HEADERS, json=profile_payload())
        connection = client.post(
            "/v1/broker-connections",
            headers=USER_HEADERS,
            json={
                "provider_id": "bybit",
                "environment": "mainnet",
                "api_key": "read-key",
                "api_secret": "read-secret-value",
            },
        ).json()

        response = client.post(
            f"/v1/broker-connections/{connection['id']}/verify", headers=USER_HEADERS
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "Bybit key has forbidden wallet permissions: Withdraw"


def test_connection_rejects_read_only_key(tmp_path):
    app = create_app(make_settings(tmp_path))
    app.state.studio.brokers.bybit = FakeBybitGateway(read_only=True)

    with TestClient(app) as client:
        client.put("/v1/me/investment-profile", headers=USER_HEADERS, json=profile_payload())
        connection = client.post(
            "/v1/broker-connections",
            headers=USER_HEADERS,
            json={
                "provider_id": "bybit",
                "environment": "mainnet",
                "api_key": "read-key",
                "api_secret": "read-secret-value",
            },
        ).json()

        response = client.post(
            f"/v1/broker-connections/{connection['id']}/verify", headers=USER_HEADERS
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "SignalOS requires a read-write Bybit API key"


def test_connection_returns_actionable_error_for_rejected_bybit_credentials(tmp_path):
    class RejectedCredentialGateway(FakeBybitGateway):
        async def get_key_info(self, **_kwargs):
            raise BrokerCredentialRejected(
                10003,
                "Bybit does not recognize this API key for the selected Test account. "
                "Create the key in Bybit Testnet and copy the matching secret. "
                "Demo Trading keys are not supported.",
            )

    app = create_app(make_settings(tmp_path))
    app.state.studio.brokers.bybit = RejectedCredentialGateway()

    with TestClient(app) as client:
        client.put("/v1/me/investment-profile", headers=USER_HEADERS, json=profile_payload())
        connection = client.post(
            "/v1/broker-connections",
            headers=USER_HEADERS,
            json={
                "provider_id": "bybit",
                "environment": "testnet",
                "api_key": "test-key",
                "api_secret": "test-secret-value",
            },
        ).json()

        response = client.post(
            f"/v1/broker-connections/{connection['id']}/verify", headers=USER_HEADERS
        )

        assert response.status_code == 422
        assert response.json()["code"] == "bybit_environment_mismatch"
        assert response.json()["detail"] == (
            "Bybit does not recognize this API key for the selected Test account. "
            "Create the key in Bybit Testnet and copy the matching secret. "
            "Demo Trading keys are not supported."
        )


def test_user_endpoints_require_identity(tmp_path):
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        assert client.get("/v1/me/onboarding-state").status_code == 401
        assert client.get("/v1/broker-providers").status_code == 401


def test_secondary_trading_credentials_endpoint_is_not_exposed(tmp_path):
    app = create_app(make_settings(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/v1/broker-connections/00000000-0000-0000-0000-000000000000/trading-credentials",
            headers=USER_HEADERS,
            json={"api_key": "trade-key", "api_secret": "trade-secret-value"},
        )

        assert response.status_code == 404


def test_user_confirmed_order_routes_are_exposed_without_agent_routes(tmp_path):
    paths = create_app(make_settings(tmp_path)).openapi()["paths"]

    assert "/v1/trade-proposals/{proposal_id}/order-review" in paths
    assert "/v1/trade-proposals/{proposal_id}/submit" in paths
    assert "/v1/orders/{order_id}" in paths
    assert "/v1/orders/{order_id}/cancel-review" in paths
    assert "/v1/orders/{order_id}/cancel" in paths
    assert "/v1/positions" in paths
    assert "/v1/positions/{position_id}/close-review" in paths
    assert "/v1/positions/{position_id}/close" in paths
    assert "/v1/positions/{position_id}/protection-review" in paths
    assert "/v1/positions/{position_id}/protection" in paths
    assert "/v1/agent/orders" not in paths


def test_notification_device_registration_never_returns_or_stores_plaintext_token(tmp_path):
    app = create_app(make_settings(tmp_path))
    installation_id = "11111111-1111-1111-1111-111111111111"
    token = "ExpoPushToken[device-token-123456789]"

    with TestClient(app) as client:
        registered = client.put(
            f"/v1/me/notification-devices/{installation_id}",
            headers=USER_HEADERS,
            json={
                "platform": "ios",
                "expo_push_token": token,
                "expo_project_id": "22222222-2222-2222-2222-222222222222",
            },
        )
        assert registered.status_code == 200
        assert "expo_push_token" not in registered.json()
        devices = client.get("/v1/me/notification-devices", headers=USER_HEADERS)
        assert devices.status_code == 200
        assert devices.json()[0]["installation_id"] == installation_id
        assert token.encode() not in (tmp_path / "studio.db").read_bytes()
        assert (
            client.delete(
                f"/v1/me/notification-devices/{installation_id}", headers=USER_HEADERS
            ).status_code
            == 204
        )


def test_bybit_connection_is_blocked_until_profile_and_disclosures_are_complete(tmp_path):
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/v1/broker-connections",
            headers=USER_HEADERS,
            json={
                "provider_id": "bybit",
                "environment": "mainnet",
                "api_key": "read-key",
                "api_secret": "read-secret-value",
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"] == (
            "complete profile and disclosures before connecting a broker"
        )


def test_revoking_active_connection_removes_studio_access(tmp_path):
    app = create_app(make_settings(tmp_path))
    app.state.studio.brokers.bybit = FakeBybitGateway()

    with TestClient(app) as client:
        client.put("/v1/me/investment-profile", headers=USER_HEADERS, json=profile_payload())
        connection = client.post(
            "/v1/broker-connections",
            headers=USER_HEADERS,
            json={
                "provider_id": "bybit",
                "environment": "mainnet",
                "api_key": "read-key",
                "api_secret": "read-secret-value",
            },
        ).json()
        client.post(f"/v1/broker-connections/{connection['id']}/verify", headers=USER_HEADERS)
        client.post(f"/v1/broker-connections/{connection['id']}/sync", headers=USER_HEADERS)

        response = client.delete(f"/v1/broker-connections/{connection['id']}", headers=USER_HEADERS)

        assert response.status_code == 204
        revoked = client.get(
            f"/v1/broker-connections/{connection['id']}", headers=USER_HEADERS
        ).json()
        assert revoked["status"] == "revoked"
        assert revoked["credential_purposes"] == []
        assert (
            client.get("/v1/me/onboarding-state", headers=USER_HEADERS).json()["studio_unlocked"]
            is False
        )
