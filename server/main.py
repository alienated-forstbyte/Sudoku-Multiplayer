
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import httpx
import redis.asyncio as redis

from server.events import RedisEventBus
from server.game_manager import GameManager
from server.protocol import validate_move
from server.repository import RedisRoomRepository

manager = GameManager()


def build_http_timeout(settings) -> httpx.Timeout:
    """Build explicit connect/read/write/pool timeouts for service calls."""
    return httpx.Timeout(
        connect=settings.service_connect_timeout,
        read=settings.service_read_timeout,
        write=settings.service_read_timeout,
        pool=settings.service_connect_timeout,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Own pooled service/Redis clients and the room event subscription."""
    redis_client = None
    if manager.settings.redis_url:
        redis_client = redis.from_url(
            manager.settings.redis_url,
            decode_responses=True,
        )
        await redis_client.ping()
        manager.repository = RedisRoomRepository(
            redis_client,
            ttl_seconds=manager.settings.redis_room_ttl_seconds,
        )
        manager.event_bus = RedisEventBus(redis_client)

    async with httpx.AsyncClient(
        timeout=build_http_timeout(manager.settings)
    ) as client:
        manager.http_client = client
        await manager.start()
        try:
            yield
        finally:
            await manager.stop()
            manager.http_client = None
            if redis_client:
                await redis_client.aclose()


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="client"), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_ui():
    with open("client/index.html") as f:
        return f.read()


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """Run one player's side of the room WebSocket protocol.

    Clients send ``move`` messages. The server emits ``init``, ``waiting``,
    ``start``, ``update``, ``game_over``, and ``error`` events documented in
    ``docs/websocket-protocol.md``.
    """
    await websocket.accept()

    # Join game
    player_id, game, _started_now = await manager.join_game(
        game_id,
        websocket,
    )

    if player_id is None:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Game full, invalid, or expired"
        }))
        await websocket.close()
        return

    # INIT
    await websocket.send_text(json.dumps({
        "type": "init",
        "player_id": player_id,
        "started": game.started,
        "difficulty": game.difficulty,
        "hash": game.puzzle_hash,
        "time_left": game.time_left(),
    }))

    # WAITING or START
    if not game.started:
        await websocket.send_text(json.dumps({
            "type": "waiting",
            "message": "Waiting for second player..."
        }))
    else:
        await manager.broadcast(game_id, {
            "type": "start",
            "board": game.board,
            "difficulty": game.difficulty,
            "time_left": game.time_left(),
            "message": "Game started!"
        })

    try:
        while True:
            # Expiry and timeout checks are message-driven: receive_text below
            # waits indefinitely, so no background task closes an idle room.
            if await manager.is_expired(game_id):
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Room expired"
                }))
                await websocket.close()
                return

            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
                continue

            game = await manager.get_game(game_id)
            if game is None:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game not found",
                }))
                continue

            # Stop if game finished
            if game.winner is not None:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game already finished"
                }))
                continue

            # Timeout check
            if await manager.check_timeout(game_id):
                game, _winner = await manager.finish_on_timeout(game_id)

                await manager.broadcast(game_id, {
                    "type": "game_over",
                    "reason": "time_up",
                    "winner": game.winner,
                    "scores": game.scores,
                })
                continue

            move, validation_error = validate_move(message)
            if validation_error:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": validation_error
                }))
                continue

            if not game.started:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game has not started"
                }))
                continue

            # Integrity check against the immutable original puzzle hash.
            try:
                puzzle_valid = await manager.verify_puzzle(game_id)
            except Exception:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Puzzle integrity service unavailable"
                }))
                continue

            if not puzzle_valid:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Puzzle integrity compromised!"
                }))
                continue

            row, col, value = move
            game, success, msg = await manager.apply_move(
                game_id,
                player_id,
                row,
                col,
                value,
            )

            response = {
                "type": "update",
                "success": success,
                "message": msg,
                "board": game.board,
                "scores": game.scores,
                "time_left": game.time_left(),
                "game_over": game.winner is not None,
                "winner": game.winner,
            }

            await manager.broadcast(game_id, response)

    except WebSocketDisconnect:
        await manager.disconnect(game_id, player_id)


@app.post("/create")
async def create_game():
    game_id = await manager.create_game()
    return {"game_id": game_id}
