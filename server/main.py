from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from server.game_manager import GameManager
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json

app = FastAPI()
manager = GameManager()

app.mount("/static", StaticFiles(directory="client"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    with open("client/index.html") as f:
        return f.read()

@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    await websocket.accept()

    # Join game
    player_id = manager.join_game(game_id, websocket)

    if player_id is None:
        await websocket.send_text("Game full or invalid")
        await websocket.close()
        return

    game = manager.get_game(game_id)

    # Send initial state
    await websocket.send_text(json.dumps({
        "type": "init",
        "player_id": player_id,
        "started": game["started"],
        "hash": game["hashes"][player_id],
        "time_left": manager.get_time_left(game_id),
        "difficulty": game["difficulties"][player_id]
    }))

    # Waiting state
    if not game["started"]:
        await websocket.send_text(json.dumps({
            "type": "waiting",
            "message": "Waiting for second player..."
        }))
    else:
        # Game just started → notify both players
        for i,player in enumerate(game["players"]):
            await player.send_text(json.dumps({
                "type": "start",
                "difficulty": game["difficulties"][i],
                "board": game["boards"][i],
                "message": "Game started!",
                "time_left": manager.get_time_left(game_id)
            }))

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
                continue
            # Stop if game already finished
            if game["winner"] is not None:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game already finished"
                }))
                continue

            # Timeout check
            if manager.check_timeout(game_id):
                if game["winner"] is None:
                    scores = game["scores"]

                    if scores[0] > scores[1]:
                        game["winner"] = 0
                    elif scores[1] > scores[0]:
                        game["winner"] = 1
                    else:
                        game["winner"] = "draw"

                for player in game["players"]:
                    await player.send_text(json.dumps({
                        "type": "game_over",
                        "reason": "time_up",
                        "winner": game["winner"],
                        "scores": game["scores"]
                    }))
                continue

            if not manager.verify_puzzle(game_id, player_id):
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Puzzle integrity compromised!"
                }))
                continue

            # Handle move
            if message["type"] == "move":
                row = message["row"]
                col = message["col"]
                value = message["value"]

                board = game["boards"][player_id]
                solution = game["solutions"][player_id]

                # Validate move
                if board[row][col] != 0:
                    success = False
                    msg = "Cell already filled"

                elif solution[row][col] != value:
                    success = False
                    msg = "Incorrect move"

                else:
                    board[row][col] = value
                    game["scores"][player_id] += 1
                    success = True
                    msg = "Correct move"

                    # Check win (this player)
                    if manager.check_win_player(game_id, player_id):
                        game["winner"] = player_id

                # Build response
                response = {
                    "type": "update",
                    "success": success,
                    "message": msg,
                    "difficulty": game["difficulties"][player_id],
                    "your_board": board,
                    "scores": game["scores"],
                    "time_left": manager.get_time_left(game_id),
                    "game_over": game["winner"] is not None,
                    "winner": game["winner"]
                }

                # Broadcast to all players
                for player in game["players"]:
                    await player.send_text(json.dumps(response))

    except WebSocketDisconnect:
        game["players"].remove(websocket)


@app.post("/create")
def create_game():
    game_id = manager.create_game()
    return {"game_id": game_id}