"""Centralized configuration via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global Sentinel configuration, loaded from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── NATS ──────────────────────────────────────────────────
    nats_url: str = "nats://localhost:4222"
    nats_max_ack_pending: int = 1000
    nats_max_deliver: int = 3
    nats_ack_wait_s: int = 30
    nats_max_msgs_per_subject: int = 10_000
    nats_max_bytes: int = 1_073_741_824  # 1 GB

    # ── TimescaleDB ───────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "sentinel"
    db_password: str = "sentinel_dev"
    db_name: str = "sentinel"
    db_pool_min: int = 5
    db_pool_max: int = 20
    db_write_batch_size: int = 500
    db_write_timeout_s: float = 5.0

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Logging ───────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "console"  # "console" or "json"

    # ── Lifecycle thresholds (seconds) ────────────────────────
    lifecycle_sweep_interval_s: float = 10.0
    aircraft_stale_s: float = 30.0
    aircraft_lost_s: float = 120.0
    vessel_stale_s: float = 300.0
    vessel_lost_s: float = 1800.0
    satellite_stale_s: float = 7200.0
    satellite_lost_s: float = 86400.0
    weather_stale_s: float = 900.0
    weather_lost_s: float = 3600.0

    # ── Ingestion rate limits (requests/second) ───────────────
    opensky_poll_interval_s: float = 10.0
    usgs_poll_interval_s: float = 60.0
    celestrak_poll_interval_s: float = 3600.0
    openmeteo_poll_interval_s: float = 300.0

    # ── API keys (optional) ───────────────────────────────────
    opensky_username: Optional[str] = None
    opensky_password: Optional[str] = None
    aisstream_api_key: Optional[str] = None

    @property
    def db_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()
