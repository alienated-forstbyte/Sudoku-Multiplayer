
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from server.game_manager import GameManager
from server.protocol import validate_move
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json

app = FastAPI()
manager = GameManager()

app.mount("/static", StaticFiles(directory="client"), name="static")


async def broadcast(game, payload: dict) -> None:
    """Send ``payload`` to every connected player, ignoring dead sockets."""
    stale = []
    message = json.dumps(payload)
    for player in list(game["players"]):
        try:
            await player.send_text(message)
        except Exception:
            stale.append(player)
    for player in stale:
        if player in game["players"]:
            game["players"].remove(player)


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
        "started": game["started"],
        "difficulty": game["difficulty"],
        "hash": game["hash"],
        "time_left": manager.get_time_left(game_id)
    }))

    # WAITING or START
    if not game["started"]:
        await websocket.send_text(json.dumps({
            "type": "waiting",
            "message": "Waiting for second player..."
        }))
    else:
        await broadcast(game, {
            "type": "start",
            "board": game["board"],
            "difficulty": game["difficulty"],
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
            if game["winner"] is not None:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game already finished"
                }))
                continue

            # Timeout check
            if manager.check_timeout(game_id):
                scores = game["scores"]

                if scores[0] > scores[1]:
                    game["winner"] = 0
                elif scores[1] > scores[0]:
                    game["winner"] = 1
                else:
                    game["winner"] = "draw"

                await broadcast(game, {
                    "type": "game_over",
                    "reason": "time_up",
                    "winner": game["winner"],
                    "scores": game["scores"]
                })
                continue

            move, validation_error = validate_move(message)
            if validation_error:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": validation_error
                }))
                continue

            if not game["started"]:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game has not started"
                }))
                continue

            # Integrity check against the immutable original puzzle hash.
            try:
                puzzle_valid = manager.verify_puzzle(game_id)
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
            board = game["board"]
            solution = game["solution"]

            if board[row][col] != 0:
                success = False
                msg = "Cell already filled"

            elif solution[row][col] != value:
                success = False
                msg = "Incorrect move"

            else:
                # Both players mutate one server-authoritative board. The
                # sender earns the point and wins if this is the final cell.
                board[row][col] = value
                game["scores"][player_id] += 1
                success = True
                msg = "Correct move"

                # Win check
                if all(0 not in r for r in board):
                    game["winner"] = player_id

            response = {
                "type": "update",
                "success": success,
                "message": msg,
                "board": board,
                "scores": game["scores"],
                "time_left": manager.get_time_left(game_id),
                "game_over": game["winner"] is not None,
                "winner": game["winner"]
            }

            await broadcast(game, response)

    except WebSocketDisconnect:
        if websocket in game["players"]:
            game["players"].remove(websocket)


@app.post("/create")
def create_game():
    game_id = manager.create_game()
    return {"game_id": game_id}
