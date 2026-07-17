import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from server.config import Settings
from server.game_manager import GameManager
from server.main import app, build_http_timeout, manager as app_manager
from server.models import RoomState, freeze_board


def test_http_timeout_has_explicit_connect_and_read_values():
    settings = Settings(
        service_connect_timeout=1.25,
        service_read_timeout=4.5,
    )

    timeout = build_http_timeout(settings)

    assert timeout.connect == 1.25
    assert timeout.read == 4.5
    assert timeout.write == 4.5
    assert timeout.pool == 1.25


def test_game_manager_uses_async_client_for_service_calls(monkeypatch):
    full_board = [[1 for _ in range(9)] for _ in range(9)]
    puzzle = [row[:] for row in full_board]
    puzzle[0][0] = 0
    requests_seen = []

    monkeypatch.setattr(
        "server.game_manager.generate_full_board",
        lambda: [row[:] for row in full_board],
    )
    monkeypatch.setattr(
        "server.game_manager.remove_numbers",
        lambda _board, _difficulty: [row[:] for row in puzzle],
    )

    async def handle(request):
        requests_seen.append((request.method, request.url.path))
        if request.url.path == "/predict":
            return httpx.Response(200, json={"difficulty": "easy"})
        if request.url.path == "/add":
            return httpx.Response(200, json={"hash": "puzzle-hash"})
        if request.url.path == "/verify":
            body = json.loads(request.content)
            assert body["hash"] == "puzzle-hash"
            return httpx.Response(200, json={"valid": True})
        return httpx.Response(404)

    async def scenario():
        settings = Settings(
            ml_service_url="http://services.test",
            blockchain_service_url="http://services.test",
        )
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle)
        ) as client:
            manager = GameManager(settings=settings, http_client=client)
            game_id = await manager.create_game()
            assert await manager.verify_puzzle(game_id) is True
            return manager.get_game(game_id)

    game = asyncio.run(scenario())

    assert requests_seen == [
        ("POST", "/predict"),
        ("POST", "/add"),
        ("POST", "/verify"),
    ]
    assert game.difficulty == "easy"
    assert game.puzzle_hash == "puzzle-hash"


def test_slow_service_call_yields_to_other_coroutines():
    events = []

    async def slow_response(_request):
        events.append("request-started")
        await asyncio.sleep(0.05)
        events.append("request-finished")
        return httpx.Response(200, json={"valid": True})

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(slow_response)
        ) as client:
            manager = GameManager(
                settings=Settings(
                    blockchain_service_url="http://services.test"
                ),
                http_client=client,
            )
            board = [[0 for _ in range(9)] for _ in range(9)]
            manager.games["game"] = RoomState(
                created_at=0,
                expiry_seconds=25,
                board=[row[:] for row in board],
                original_board=freeze_board(board),
                solution=[[1 for _ in range(9)] for _ in range(9)],
                difficulty="easy",
                puzzle_hash="hash",
                time_limit_seconds=600,
            )

            async def heartbeat():
                await asyncio.sleep(0.01)
                events.append("heartbeat")

            valid, _ = await asyncio.gather(
                manager.verify_puzzle("game"),
                heartbeat(),
            )
            assert valid is True

    asyncio.run(scenario())

    assert events == ["request-started", "heartbeat", "request-finished"]


def test_create_endpoint_awaits_game_manager(monkeypatch):
    async def fake_create_game():
        return "async-game"

    monkeypatch.setattr(app_manager, "create_game", fake_create_game)

    with TestClient(app) as client:
        response = client.post("/create")

    assert response.status_code == 200
    assert response.json() == {"game_id": "async-game"}
