from __future__ import annotations

import logfire
from sqlalchemy.ext.asyncio import AsyncEngine

from signalos_backend.config import Settings

_configured = False

_SECRET_PATTERNS = (
    "x-bapi-sign",
    "x-bapi-api-key",
    "identity-signature",
    "step-up-proof",
    "step_up_proof",
    "ciphertext",
    "expo_push_token",
)


def configure_observability(
    *,
    settings: Settings,
    engine: AsyncEngine,
    service_name: str,
) -> bool:
    """Configure shared telemetry once for the current process."""
    global _configured
    if settings.environment == "test" or _configured:
        return False

    logfire.configure(
        service_name=service_name,
        environment=settings.environment,
        send_to_logfire=settings.logfire_send,
        console=False,
        inspect_arguments=False,
        scrubbing=logfire.ScrubbingOptions(extra_patterns=_SECRET_PATTERNS),
    )
    # Agent prompts can contain portfolio/profile context. Trace timing, model
    # identity, token usage, and failures without exporting message content.
    logfire.instrument_pydantic_ai(include_content=False, include_binary_content=False)
    logfire.instrument_httpx()
    logfire.instrument_sqlalchemy(engine.sync_engine)
    _configured = True
    return True


def flush_observability(*, timeout_millis: int = 3_000) -> bool:
    """Flush buffered worker telemetry before a short-lived process exits."""
    if not _configured:
        return True
    return logfire.force_flush(timeout_millis=timeout_millis)
