from __future__ import annotations

import base64
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from signalos_backend.db import IntelligenceStore, build_engine
from signalos_backend.notifications.domain import (
    DevicePlatform,
    PushDeviceStatus,
    RegisterPushDevice,
)
from signalos_backend.notifications.gateway import ExpoPushGateway
from signalos_backend.notifications.service import NotificationService
from signalos_backend.notifications.store import NotificationStore
from signalos_backend.proposals.domain import OrderSide
from signalos_backend.security.credentials import CredentialCipher


@pytest.mark.asyncio
async def test_expo_device_is_encrypted_and_receipt_disables_invalid_token(tmp_path):
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read()
        requests.append({"path": request.url.path, "body": payload.decode()})
        if request.url.path.endswith("/send"):
            return httpx.Response(
                200,
                json={"data": [{"status": "ok", "id": "expo-ticket-1"}]},
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "expo-ticket-1": {
                        "status": "error",
                        "message": "device is no longer registered",
                        "details": {"error": "DeviceNotRegistered"},
                    }
                }
            },
        )

    database_path = tmp_path / "notifications.db"
    engine = build_engine(f"sqlite+aiosqlite:///{database_path}")
    database = IntelligenceStore(engine)
    await database.create_schema()
    cipher = CredentialCipher(
        (base64.urlsafe_b64encode(b"notification-test-key-material-0").decode(),)
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    gateway = ExpoPushGateway(access_token="expo-access", client=client)
    service = NotificationService(
        store=NotificationStore(database.sessions),
        cipher=cipher,
        gateway=gateway,
        clock=lambda: datetime(2026, 8, 15, 12, tzinfo=UTC),
    )
    installation_id = uuid4()
    token = "ExpoPushToken[testing-token-123456789]"

    device = await service.register_device(
        user_id="user-a",
        installation_id=installation_id,
        payload=RegisterPushDevice(
            platform=DevicePlatform.IOS,
            expo_push_token=token,
            expo_project_id=UUID("11111111-1111-1111-1111-111111111111"),
        ),
    )
    await service.notify_proposal(
        SimpleNamespace(id=uuid4(), user_id="user-a", side=OrderSide.BUY, symbol="BTCUSDT")
    )
    reconciled = await service.reconcile_receipts()

    assert device.status is PushDeviceStatus.ACTIVE
    assert reconciled == 1
    assert (await service.list_devices(user_id="user-a"))[0].status is PushDeviceStatus.DISABLED
    assert token not in database_path.read_text(errors="ignore")
    assert [request["path"] for request in requests] == [
        "/--/api/v2/push/send",
        "/--/api/v2/push/getReceipts",
    ]
    assert token in str(requests[0]["body"])
    assert "BTCUSDT" not in str(requests[0]["body"])
    assert "Buy" not in str(requests[0]["body"])
    await client.aclose()
    await engine.dispose()


@pytest.mark.asyncio
async def test_device_registration_cannot_replace_another_users_installation(tmp_path):
    engine = build_engine(f"sqlite+aiosqlite:///{tmp_path / 'device-isolation.db'}")
    database = IntelligenceStore(engine)
    await database.create_schema()
    cipher = CredentialCipher(
        (base64.urlsafe_b64encode(b"notification-test-key-material-0").decode(),)
    )
    service = NotificationService(
        store=NotificationStore(database.sessions),
        cipher=cipher,
        gateway=ExpoPushGateway(
            access_token="expo-access",
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))),
        ),
    )
    installation_id = uuid4()
    await service.register_device(
        user_id="user-a",
        installation_id=installation_id,
        payload=RegisterPushDevice(
            platform=DevicePlatform.IOS,
            expo_push_token="ExpoPushToken[user-a-token-123456789]",
            expo_project_id=uuid4(),
        ),
    )

    with pytest.raises(PermissionError, match="another user"):
        await service.register_device(
            user_id="user-b",
            installation_id=installation_id,
            payload=RegisterPushDevice(
                platform=DevicePlatform.IOS,
                expo_push_token="ExpoPushToken[user-b-token-123456789]",
                expo_project_id=uuid4(),
            ),
        )

    assert len(await service.list_devices(user_id="user-a")) == 1
    assert await service.list_devices(user_id="user-b") == ()
    await service.gateway.client.aclose()
    await engine.dispose()


def test_invalid_expo_token_is_rejected_before_persistence():
    with pytest.raises(ValueError, match="invalid Expo push token"):
        RegisterPushDevice(
            platform=DevicePlatform.ANDROID,
            expo_push_token="not-an-expo-push-token",
            expo_project_id=uuid4(),
        )
