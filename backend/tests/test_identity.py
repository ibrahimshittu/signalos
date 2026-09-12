from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm
from pydantic import ValidationError

from signalos_backend.config import Settings
from signalos_backend.identity import SupabaseAccessTokenVerifier
from signalos_backend.main import create_app

TEST_ENCRYPTION_KEY = base64.urlsafe_b64encode(b"signalos-test-key-material-00000").decode()


def test_internal_api_url_defaults_to_port_8001():
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite+aiosqlite:///:memory:",
    )

    assert settings.api_base_url == "http://api:8001"


def test_production_settings_require_supabase_and_real_secrets():
    with pytest.raises(ValidationError):
        Settings(environment="production")


def test_development_settings_reject_sqlite_runtime():
    with pytest.raises(ValidationError, match="Supabase PostgreSQL"):
        Settings(
            environment="development",
            database_url="sqlite+aiosqlite:///./signalos.db",
            api_key="test-admin-key-with-at-least-thirty-two-characters",
            credential_encryption_key=TEST_ENCRYPTION_KEY,
            expo_access_token="test-expo-access-token",
            supabase_url="https://project.supabase.co",
        )


def test_settings_repr_redacts_runtime_secrets():
    settings = Settings(
        environment="test",
        database_url="postgresql+asyncpg://postgres:database-password@localhost/postgres",
        api_key="operator-secret-value",
        openrouter_api_key="model-provider-secret-value",
    )

    rendered = repr(settings)
    assert "database-password" not in rendered
    assert "operator-secret-value" not in rendered
    assert "model-provider-secret-value" not in rendered


def test_test_identity_is_explicitly_test_only(tmp_path):
    app = create_app(
        Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'identity.db'}",
        )
    )
    with TestClient(app) as client:
        response = client.get(
            "/v1/me/onboarding-state",
            headers={"X-SignalOS-User-Id": "user-a"},
        )
        assert response.status_code == 200
        assert client.get("/v1/me/onboarding-state").status_code == 401


@pytest.mark.asyncio
async def test_supabase_bearer_token_is_verified_against_project_jwks(tmp_path):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"alg": "RS256", "kid": "test-key", "use": "sig"})
    settings = Settings(
        environment="development",
        api_key="test-admin-key-with-at-least-thirty-two-characters",
        credential_encryption_key=TEST_ENCRYPTION_KEY,
        expo_access_token="test-expo-access-token",
        supabase_url="https://project.supabase.co",
        database_url="postgresql+asyncpg://postgres:password@localhost:5432/postgres",
    )
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "aud": "authenticated",
            "exp": now + timedelta(minutes=5),
            "iat": now,
            "iss": "https://project.supabase.co/auth/v1",
            "role": "authenticated",
            "sub": "c481a580-f01a-40ab-a91a-0b34a5c6e475",
            "aal": "aal2",
            "amr": [
                {"method": "password", "timestamp": int((now - timedelta(minutes=1)).timestamp())},
                {"method": "totp", "timestamp": int(now.timestamp())},
            ],
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )

    def jwks(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/.well-known/jwks.json"
        return httpx.Response(200, json={"keys": [public_jwk]})

    verifier = SupabaseAccessTokenVerifier(
        settings,
        client=httpx.AsyncClient(transport=httpx.MockTransport(jwks)),
    )
    principal = await verifier.verify(token)
    assert principal.user_id == "c481a580-f01a-40ab-a91a-0b34a5c6e475"
    assert principal.assurance_level == "aal2"
    assert principal.mfa_verified_at == datetime.fromtimestamp(int(now.timestamp()), UTC)
    await verifier.client.aclose()


@pytest.mark.asyncio
async def test_supabase_auth_rejects_wrong_audience(tmp_path):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"alg": "RS256", "kid": "test-key", "use": "sig"})
    settings = Settings(
        environment="development",
        api_key="test-admin-key-with-at-least-thirty-two-characters",
        credential_encryption_key=TEST_ENCRYPTION_KEY,
        expo_access_token="test-expo-access-token",
        supabase_url="https://project.supabase.co",
        database_url="postgresql+asyncpg://postgres:password@localhost:5432/postgres",
    )
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "aud": "other",
            "exp": now + timedelta(minutes=5),
            "iat": now,
            "iss": "https://project.supabase.co/auth/v1",
            "role": "authenticated",
            "sub": "c481a580-f01a-40ab-a91a-0b34a5c6e475",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    verifier = SupabaseAccessTokenVerifier(
        settings,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json={"keys": [public_jwk]})
            )
        ),
    )
    with pytest.raises(ValueError, match="invalid Supabase access token"):
        await verifier.verify(token)
    await verifier.client.aclose()
