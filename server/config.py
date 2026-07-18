"""Application settings resolved from environment variables.

Every value has a development default so ``docker compose up`` and the test
suite work with no configuration. Production deployments override these through
the environment instead of editing source.
"""

import os
from dataclasses import dataclass


def _get_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _get_optional_str(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else None


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be a number, got {raw!r}") from error


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from error


@dataclass(frozen=True)
class Settings:
    """Typed runtime configuration for the game server."""

    ml_service_url: str = "http://ml_service:8001"
    blockchain_service_url: str = "http://blockchain:8002"
    service_connect_timeout: float = 2.0
    service_read_timeout: float = 5.0
    room_expiry_seconds: int = 25
    game_time_limit_seconds: int = 600
    redis_url: str | None = None
    redis_room_ttl_seconds: int = 3600
    scheduler_poll_interval: float = 1.0

    @property
    def predict_url(self) -> str:
        return f"{self.ml_service_url.rstrip('/')}/predict"

    @property
    def blockchain_add_url(self) -> str:
        return f"{self.blockchain_service_url.rstrip('/')}/add"

    @property
    def blockchain_verify_url(self) -> str:
        return f"{self.blockchain_service_url.rstrip('/')}/verify"


def load_settings() -> Settings:
    """Build a :class:`Settings` instance from the current environment."""
    return Settings(
        ml_service_url=_get_str("ML_SERVICE_URL", Settings.ml_service_url),
        blockchain_service_url=_get_str(
            "BLOCKCHAIN_SERVICE_URL", Settings.blockchain_service_url
        ),
        service_connect_timeout=_get_float(
            "SERVICE_CONNECT_TIMEOUT", Settings.service_connect_timeout
        ),
        service_read_timeout=_get_float(
            "SERVICE_READ_TIMEOUT", Settings.service_read_timeout
        ),
        room_expiry_seconds=_get_int(
            "ROOM_EXPIRY_SECONDS", Settings.room_expiry_seconds
        ),
        game_time_limit_seconds=_get_int(
            "GAME_TIME_LIMIT_SECONDS", Settings.game_time_limit_seconds
        ),
        redis_url=_get_optional_str("REDIS_URL"),
        redis_room_ttl_seconds=_get_int(
            "REDIS_ROOM_TTL_SECONDS", Settings.redis_room_ttl_seconds
        ),
        scheduler_poll_interval=_get_float(
            "SCHEDULER_POLL_INTERVAL", Settings.scheduler_poll_interval
        ),
    )
