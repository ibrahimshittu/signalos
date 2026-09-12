from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Protocol

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from jwt import InvalidTokenError, PyJWK

from signalos_backend.config import Settings

_DEVELOPMENT_USER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,199}$")
_BEARER = re.compile(r"^Bearer ([^\s]+)$", re.IGNORECASE)
_ALLOWED_ALGORITHMS = frozenset({"ES256", "RS256"})


@dataclass(frozen=True)
class Principal:
    user_id: str
    assurance_level: str = "aal1"
    mfa_verified_at: datetime | None = None


class AccessTokenVerifier(Protocol):
    async def verify(self, token: str) -> Principal: ...


class SupabaseAccessTokenVerifier:
    """Verify Supabase access tokens locally against the project's public JWKS."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not settings.supabase_url:
            raise ValueError("Supabase URL is required")
        self.issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1"
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"
        self.audience = settings.supabase_jwt_audience
        self.cache_seconds = settings.supabase_jwks_cache_seconds
        self.client = client or httpx.AsyncClient(timeout=5.0)
        self._owns_client = client is None
        self._keys: dict[str, dict[str, Any]] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
            key_id = header.get("kid")
            algorithm = header.get("alg")
            if not isinstance(key_id, str) or algorithm not in _ALLOWED_ALGORITHMS:
                raise InvalidTokenError("unsupported signing key")
            jwk = await self._get_key(key_id)
            if jwk.get("alg") not in (None, algorithm):
                raise InvalidTokenError("signing algorithm mismatch")
            claims = jwt.decode(
                token,
                key=PyJWK.from_dict(jwk, algorithm=algorithm).key,
                algorithms=[algorithm],
                audience=self.audience,
                issuer=self.issuer,
                leeway=30,
                options={"require": ["aud", "exp", "iat", "iss", "role", "sub"]},
            )
        except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid Supabase access token") from exc
        if claims.get("role") != "authenticated":
            raise ValueError("invalid Supabase access token")
        user_id = claims["sub"]
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("invalid Supabase access token")
        assurance_level = claims.get("aal", "aal1")
        if assurance_level not in {"aal1", "aal2"}:
            assurance_level = "aal1"
        mfa_verified_at = _mfa_verified_at(claims.get("amr"))
        return Principal(
            user_id=user_id,
            assurance_level=assurance_level,
            mfa_verified_at=mfa_verified_at,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _get_key(self, key_id: str) -> dict[str, Any]:
        now = time.monotonic()
        if now >= self._expires_at or key_id not in self._keys:
            async with self._lock:
                now = time.monotonic()
                if now >= self._expires_at or key_id not in self._keys:
                    response = await self.client.get(self.jwks_url)
                    response.raise_for_status()
                    payload = response.json()
                    keys = payload.get("keys") if isinstance(payload, dict) else None
                    if not isinstance(keys, list):
                        raise ValueError("invalid Supabase JWKS response")
                    self._keys = {
                        key["kid"]: key
                        for key in keys
                        if isinstance(key, dict) and isinstance(key.get("kid"), str)
                    }
                    self._expires_at = now + self.cache_seconds
        try:
            return self._keys[key_id]
        except KeyError as exc:
            raise ValueError("unknown Supabase signing key") from exc


async def require_principal(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_signalos_user_id: Annotated[str | None, Header()] = None,
) -> Principal:
    """Resolve a test identity or validate a Supabase Bearer token."""

    settings: Settings = request.app.state.settings
    if settings.environment == "test":
        if x_signalos_user_id and _DEVELOPMENT_USER_ID.fullmatch(x_signalos_user_id):
            return Principal(
                user_id=x_signalos_user_id,
                assurance_level="aal2",
                mfa_verified_at=datetime.now(UTC),
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="test identity required",
        )

    match = _BEARER.fullmatch(authorization or "")
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return await request.app.state.access_token_verifier.verify(match.group(1))
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def require_execution_principal(
    request: Request,
    principal: Annotated[Principal, Depends(require_principal)],
) -> Principal:
    """Require a recently verified Supabase MFA factor for a broker mutation."""

    settings: Settings = request.app.state.settings
    if settings.environment == "test":
        return principal
    verified_at = principal.mfa_verified_at
    if (
        principal.assurance_level != "aal2"
        or verified_at is None
        or datetime.now(UTC) - verified_at
        > timedelta(seconds=settings.execution_step_up_max_age_seconds)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="recent multi-factor authentication required",
        )
    return principal


def _mfa_verified_at(value: object) -> datetime | None:
    if not isinstance(value, list):
        return None
    timestamps = [
        item.get("timestamp")
        for item in value
        if isinstance(item, dict)
        and item.get("method") in {"totp", "phone", "webauthn"}
        and isinstance(item.get("timestamp"), (int, float))
    ]
    return datetime.fromtimestamp(max(timestamps), UTC) if timestamps else None
