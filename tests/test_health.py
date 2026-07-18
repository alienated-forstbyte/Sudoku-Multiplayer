"""Tests for health, metrics, and correlation-ID endpoints."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from server.config import Settings
from server.events import InMemoryEventBus
from server.main import app, manager
from server.repository import InMemoryRoomRepository


@pytest.fixture(autouse=True)
def isolated_manager():
    manager.repository = InMemoryRoomRepository()
    manager.event_bus = InMemoryEventBus()
    manager.local_connections.clear()
    manager._redis_client = None
    original_settings = manager.settings
    yield
    manager.local_connections.clear()
    manager._redis_client = None
    manager.settings = original_settings


def _make_fake_redis_ping(return_value=True, side_effect=None):
    """Return an async function that mimics manager.redis_ping."""
    async def fake_ping():
        if side_effect:
            raise side_effect
        return return_value
    return fake_ping


def test_health_no_redis():
    manager.settings = replace(manager.settings, redis_url=None)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["checks"] == {}


def test_health_redis_ok(monkeypatch):
    manager.settings = replace(manager.settings, redis_url=None)

    manager._redis_client = object()
    manager.redis_ping = _make_fake_redis_ping(return_value=True)

    # Bypass lifespan by calling the endpoint logic directly.
    # We need settings.redis_url to be truthy for the health handler to
    # enter the redis branch, but we cannot have the lifespan connect to
    # real Redis.  So we set redis_url back after the lifespan runs.
    from starlette.testclient import TestClient as _TC
    with _TC(app, raise_server_exceptions=False) as client:
        # Replace settings just for this request — the lifespan already
        # ran with redis_url=None so no real connection was made.
        manager.settings = replace(manager.settings, redis_url="redis://localhost:6379/0")
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["checks"]["redis"] == "ok"

    manager.settings = replace(manager.settings, redis_url=None)


def test_health_returns_correlation_id_header():
    manager.settings = replace(manager.settings, redis_url=None)

    with TestClient(app) as client:
        response = client.get("/health", headers={"x-correlation-id": "abc123"})

    assert response.headers["x-correlation-id"] == "abc123"


def test_health_generates_correlation_id_when_missing():
    manager.settings = replace(manager.settings, redis_url=None)

    with TestClient(app) as client:
        response = client.get("/health")

    cid = response.headers.get("x-correlation-id")
    assert cid is not None
    assert len(cid) == 12


def test_health_degraded_when_redis_unreachable(monkeypatch):
    manager.settings = replace(manager.settings, redis_url=None)

    manager._redis_client = object()
    manager.redis_ping = _make_fake_redis_ping(return_value=False)

    with TestClient(app) as client:
        manager.settings = replace(manager.settings, redis_url="redis://localhost:6379/0")
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"] == "degraded"

    manager.settings = replace(manager.settings, redis_url=None)


def test_health_degraded_when_redis_ping_raises(monkeypatch):
    manager.settings = replace(manager.settings, redis_url=None)

    manager._redis_client = object()
    manager.redis_ping = _make_fake_redis_ping(side_effect=ConnectionError("refused"))

    with TestClient(app) as client:
        manager.settings = replace(manager.settings, redis_url="redis://localhost:6379/0")
        response = client.get("/health")

    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"] == "unhealthy"

    manager.settings = replace(manager.settings, redis_url=None)


def test_metrics_endpoint_returns_prometheus_text():
    manager.settings = replace(manager.settings, redis_url=None)

    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "sudoku_games_created_total" in response.text


def test_health_does_not_touch_repository():
    manager.settings = replace(manager.settings, redis_url=None)

    class FailRepository:
        def __getattr__(self, name):
            raise AssertionError(f"repository.{name} called unexpectedly")

    original = manager.repository
    manager.repository = FailRepository()
    try:
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
    finally:
        manager.repository = original
