from types import SimpleNamespace

from signalos_backend.config import Settings
from signalos_backend.observability import configure_observability


def test_agent_telemetry_excludes_user_and_portfolio_content(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("signalos_backend.observability._configured", False)
    monkeypatch.setattr("signalos_backend.observability.logfire.configure", lambda **_kwargs: None)
    monkeypatch.setattr(
        "signalos_backend.observability.logfire.instrument_pydantic_ai",
        lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr("signalos_backend.observability.logfire.instrument_httpx", lambda: None)
    monkeypatch.setattr(
        "signalos_backend.observability.logfire.instrument_sqlalchemy", lambda _engine: None
    )

    configured = configure_observability(
        settings=Settings.model_construct(environment="development", logfire_send=True),
        engine=SimpleNamespace(sync_engine=object()),
        service_name="signalos-market-worker",
    )

    assert configured is True
    assert calls == [{"include_content": False, "include_binary_content": False}]
