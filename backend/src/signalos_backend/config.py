from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SIGNALOS_",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    database_url: SecretStr
    api_key: SecretStr = SecretStr("change-me")
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    producer_model: str = "openai/gpt-5.2"
    verifier_model: str = "anthropic/claude-opus-4-6"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_enabled: bool = False
    api_base_url: str = "http://api:8001"
    temporal_research_queue: str = "signalos-research"
    temporal_portfolio_queue: str = "signalos-portfolio"
    temporal_execution_queue: str = "signalos-execution-disabled"
    logfire_send: bool = False
    max_question_length: int = Field(default=4_000, ge=100, le=20_000)
    managed_assets: tuple[str, ...] = ("BTC", "ETH", "SOL", "USDC")
    supabase_url: str | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_cache_seconds: int = Field(default=600, ge=60, le=3_600)
    credential_encryption_key: SecretStr | None = None
    credential_previous_encryption_keys: tuple[SecretStr, ...] = ()
    expo_access_token: SecretStr | None = None
    expo_push_base_url: str = "https://exp.host/--/api/v2/push"
    expo_receipt_interval_seconds: int = Field(default=900, ge=60, le=3_600)
    bybit_mainnet_base_url: str = "https://api.bybit.com"
    bybit_testnet_base_url: str = "https://api-testnet.bybit.com"
    bybit_recv_window_ms: int = Field(default=5_000, ge=1_000, le=10_000)
    bybit_timeout_seconds: float = Field(default=10, gt=0, le=60)
    execution_reconciliation_interval_seconds: int = Field(default=5, ge=2, le=60)
    execution_step_up_max_age_seconds: int = Field(default=300, ge=60, le=900)
    market_scan_interval_seconds: int = Field(default=60, ge=30, le=300)
    market_analysis_interval_seconds: int = Field(default=300, ge=60, le=3_600)
    market_analysis_max_candidates: int = Field(default=5, ge=1, le=20)
    market_analysis_candle_interval_minutes: int = Field(default=15, ge=1, le=720)
    market_analysis_candle_limit: int = Field(default=200, ge=50, le=1_000)
    market_data_max_age_seconds: int = Field(default=30, ge=5, le=300)
    instrument_refresh_seconds: int = Field(default=21_600, ge=300, le=86_400)

    @field_validator("market_analysis_candle_interval_minutes")
    @classmethod
    def validate_bybit_candle_interval(cls, value: int) -> int:
        if value not in {1, 3, 5, 15, 30, 60, 120, 240, 360, 720}:
            raise ValueError("unsupported Bybit candle interval")
        return value

    @model_validator(mode="after")
    def require_runtime_settings(self) -> "Settings":
        if self.environment == "test":
            return self
        missing: list[str] = []
        database_url = self.database_url.get_secret_value()
        api_key = self.api_key.get_secret_value()
        if not database_url.startswith("postgresql+asyncpg://"):
            missing.append("a Supabase PostgreSQL URL using postgresql+asyncpg://")
        if api_key == "change-me" or len(api_key) < 32:
            missing.append("a unique admin API key of at least 32 characters")
        if not self.supabase_url:
            missing.append("SIGNALOS_SUPABASE_URL")
        if self.credential_encryption_key is None:
            missing.append("a broker credential encryption key")
        if self.expo_access_token is None:
            missing.append("SIGNALOS_EXPO_ACCESS_TOKEN")
        if missing:
            message = f"{self.environment} configuration requires " + "; ".join(missing)
            raise ValueError(message)
        return self

    @model_validator(mode="after")
    def validate_supabase_auth(self) -> "Settings":
        if self.environment == "test":
            return self
        if not self.supabase_url:
            raise ValueError("Supabase authentication requires SIGNALOS_SUPABASE_URL")
        if not self.supabase_url.startswith("https://"):
            raise ValueError("SIGNALOS_SUPABASE_URL must use HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
