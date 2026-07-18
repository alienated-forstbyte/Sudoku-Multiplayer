"""Tests for graceful degradation when ML or blockchain services are unavailable."""

import asyncio
import time
from unittest.mock import MagicMock

import httpx
import pytest
from unittest.mock import AsyncMock

from server.config import Settings
from server.events import InMemoryEventBus
from server.game_manager import GameManager
from server.models import RoomState, freeze_board
from server.repository import InMemoryRoomRepository


def _make_sync_response(json_data=None, status_code=200):
    """Create a mock response with sync raise_for_status() and json()."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def manager_with_degraded():
    settings = Settings(allow_degraded_creation=True)
    return GameManager(settings=settings, http_client=AsyncMock(spec=httpx.AsyncClient))


@pytest.fixture
def manager_strict():
    settings = Settings(allow_degraded_creation=False)
    return GameManager(settings=settings, http_client=AsyncMock(spec=httpx.AsyncClient))


def _seed_room(manager, game_id="test-game"):
    solution = [[1 for _ in range(9)] for _ in range(9)]
    board = [row[:] for row in solution]
    board[0][0] = 0
    room = RoomState(
        created_at=time.time(),
        expiry_seconds=25,
        board=board,
        original_board=freeze_board(board),
        solution=solution,
        difficulty="easy",
        puzzle_hash="test-hash",
        time_limit_seconds=600,
    )
    asyncio.run(manager.repository.create(game_id, room))
    return room


# ------------------------------------------------------------------
# create_game — ML failure
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_game_ml_down_degraded(manager_with_degraded):
    manager_with_degraded.http_client.post = AsyncMock(
        side_effect=httpx.ConnectError("refused")
    )

    game_id = await manager_with_degraded.create_game()

    room = await manager_with_degraded.repository.get(game_id)
    assert room is not None
    assert room.difficulty in ("easy", "medium", "hard")


@pytest.mark.asyncio
async def test_create_game_ml_down_strict_raises(manager_strict):
    manager_strict.http_client.post = AsyncMock(
        side_effect=httpx.ConnectError("refused")
    )

    with pytest.raises(httpx.ConnectError):
        await manager_strict.create_game()


# ------------------------------------------------------------------
# create_game — blockchain failure
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_game_blockchain_down_degraded(manager_with_degraded):
    async def post_side_effect(url, **kwargs):
        if "predict" in url:
            return _make_sync_response({"difficulty": "medium"})
        raise httpx.ConnectError("refused")

    manager_with_degraded.http_client.post = post_side_effect

    game_id = await manager_with_degraded.create_game()

    room = await manager_with_degraded.repository.get(game_id)
    assert room is not None
    assert room.puzzle_hash == ""


@pytest.mark.asyncio
async def test_create_game_blockchain_down_strict_raises():
    settings = Settings(allow_degraded_creation=False)
    mgr = GameManager(settings=settings, http_client=AsyncMock(spec=httpx.AsyncClient))

    async def post_side_effect(url, **kwargs):
        if "predict" in url:
            return _make_sync_response({"difficulty": "medium"})
        raise httpx.ConnectError("refused")

    mgr.http_client.post = post_side_effect

    with pytest.raises(httpx.ConnectError):
        await mgr.create_game()


# ------------------------------------------------------------------
# create_game — both services down
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_game_both_down_degraded(manager_with_degraded):
    manager_with_degraded.http_client.post = AsyncMock(
        side_effect=httpx.ConnectError("refused")
    )

    game_id = await manager_with_degraded.create_game()

    room = await manager_with_degraded.repository.get(game_id)
    assert room is not None
    assert room.puzzle_hash == ""


# ------------------------------------------------------------------
# create_game — both services healthy
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_game_both_up():
    settings = Settings()
    mgr = GameManager(settings=settings, http_client=AsyncMock(spec=httpx.AsyncClient))

    async def post_side_effect(url, **kwargs):
        if "predict" in url:
            return _make_sync_response({"difficulty": "hard"})
        return _make_sync_response({"hash": "abc123"})

    mgr.http_client.post = post_side_effect

    game_id = await mgr.create_game()

    room = await mgr.repository.get(game_id)
    assert room is not None
    assert room.difficulty == "hard"
    assert room.puzzle_hash == "abc123"


# ------------------------------------------------------------------
# redis_ping
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redis_ping_returns_true_when_no_client():
    settings = Settings()
    mgr = GameManager(settings=settings)
    assert await mgr.redis_ping() is True


@pytest.mark.asyncio
async def test_redis_ping_delegates_to_client():
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    settings = Settings()
    mgr = GameManager(settings=settings)
    mgr.set_redis_client(mock_redis)

    assert await mgr.redis_ping() is True
    mock_redis.ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_ping_returns_false_on_error():
    mock_redis = AsyncMock()
    mock_redis.ping.side_effect = ConnectionError("refused")
    settings = Settings()
    mgr = GameManager(settings=settings)
    mgr.set_redis_client(mock_redis)

    assert await mgr.redis_ping() is False
