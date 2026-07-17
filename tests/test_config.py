import pytest

from server.config import Settings, load_settings
from server.game_manager import GameManager


def test_defaults_match_compose_service_names(monkeypatch):
    for name in (
        "ML_SERVICE_URL",
        "BLOCKCHAIN_SERVICE_URL",
        "SERVICE_CONNECT_TIMEOUT",
        "SERVICE_READ_TIMEOUT",
        "ROOM_EXPIRY_SECONDS",
        "GAME_TIME_LIMIT_SECONDS",
        "REDIS_URL",
        "REDIS_ROOM_TTL_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert settings.ml_service_url == "http://ml_service:8001"
    assert settings.blockchain_service_url == "http://blockchain:8002"
    assert settings.service_connect_timeout == 2.0
    assert settings.service_read_timeout == 5.0
    assert settings.room_expiry_seconds == 25
    assert settings.game_time_limit_seconds == 600
    assert settings.redis_url is None
    assert settings.redis_room_ttl_seconds == 3600


def test_environment_overrides_are_applied(monkeypatch):
    monkeypatch.setenv("ML_SERVICE_URL", "http://ml.internal:9101/")
    monkeypatch.setenv("BLOCKCHAIN_SERVICE_URL", "http://chain.internal:9102")
    monkeypatch.setenv("SERVICE_CONNECT_TIMEOUT", "1.5")
    monkeypatch.setenv("SERVICE_READ_TIMEOUT", "2.5")
    monkeypatch.setenv("ROOM_EXPIRY_SECONDS", "40")
    monkeypatch.setenv("GAME_TIME_LIMIT_SECONDS", "120")
    monkeypatch.setenv("REDIS_URL", "redis://cache.internal:6379/2")
    monkeypatch.setenv("REDIS_ROOM_TTL_SECONDS", "7200")

    settings = load_settings()

    assert settings.service_connect_timeout == 1.5
    assert settings.service_read_timeout == 2.5
    assert settings.room_expiry_seconds == 40
    assert settings.game_time_limit_seconds == 120
    assert settings.redis_url == "redis://cache.internal:6379/2"
    assert settings.redis_room_ttl_seconds == 7200
    # Derived URLs normalize trailing slashes.
    assert settings.predict_url == "http://ml.internal:9101/predict"
    assert settings.blockchain_add_url == "http://chain.internal:9102/add"
    assert settings.blockchain_verify_url == "http://chain.internal:9102/verify"


def test_invalid_numeric_setting_is_rejected(monkeypatch):
    monkeypatch.setenv("ROOM_EXPIRY_SECONDS", "not-a-number")

    with pytest.raises(ValueError):
        load_settings()


def test_game_manager_uses_injected_settings():
    settings = Settings(
        room_expiry_seconds=99,
        game_time_limit_seconds=111,
    )

    manager = GameManager(settings=settings)

    assert manager.settings is settings
    assert manager.settings.room_expiry_seconds == 99
    assert manager.settings.game_time_limit_seconds == 111
