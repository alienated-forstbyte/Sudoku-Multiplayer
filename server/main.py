
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import httpx

from server.game_manager import GameManager
from server.models import RoomState
from server.protocol import validate_move

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
    """Own one pooled async client for the game server process."""
    async with httpx.AsyncClient(
        timeout=build_http_timeout(manager.settings)
    ) as client:
        manager.http_client = client
        try:
            yield
        finally:
            manager.http_client = None


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="client"), name="static")


async def broadcast(game: RoomState, payload: dict) -> None:
    """Send ``payload`` to every connected player, ignoring dead sockets."""
    stale = []
    message = json.dumps(payload)
    for player in list(game.players):
        try:
            await player.send_text(message)
        except Exception:
            stale.append(player)
    for player in stale:
        game.remove_player(player)


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
    player_id = manager.join_game(game_id, websocket)

    if player_id is None:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Game full, invalid, or expired"
        }))
        await websocket.close()
        return

    game = manager.get_game(game_id)

    # INIT
    await websocket.send_text(json.dumps({
        "type": "init",
        "player_id": player_id,
        "started": game.started,
        "difficulty": game.difficulty,
        "hash": game.puzzle_hash,
        "time_left": manager.get_time_left(game_id)
    }))

    # WAITING or START
    if not game.started:
        await websocket.send_text(json.dumps({
            "type": "waiting",
            "message": "Waiting for second player..."
        }))
    else:
        await broadcast(game, {
            "type": "start",
            "board": game.board,
            "difficulty": game.difficulty,
            "time_left": manager.get_time_left(game_id),
            "message": "Game started!"
        })

    try:
        while True:
            # Expiry and timeout checks are message-driven: receive_text below
            # waits indefinitely, so no background task closes an idle room.
            if manager.is_expired(game_id):
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

            # Stop if game finished
            if game.winner is not None:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game already finished"
                }))
                continue

            # Timeout check
            if manager.check_timeout(game_id):
                game.finish_on_timeout()

                await broadcast(game, {
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
            success, msg = game.apply_move(player_id, row, col, value)

            response = {
                "type": "update",
                "success": success,
                "message": msg,
                "board": game.board,
                "scores": game.scores,
                "time_left": manager.get_time_left(game_id),
                "game_over": game.winner is not None,
                "winner": game.winner,
            }

            await broadcast(game, response)

    except WebSocketDisconnect:
        game.remove_player(websocket)


@app.post("/create")
async def create_game():
    game_id = await manager.create_game()
    return {"game_id": game_id}
