from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from server.game_manager import GameManager
import json

app = FastAPI()
manager = GameManager()


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
        "board": game["board"],
        "player_id": player_id,
        "your_turn": game["turn"] == player_id,
        "time_left": manager.get_time_left(game_id)
    }))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Stop if game already finished
            if game["winner"] is not None:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game already finished"
                }))
                continue

            # ⏱ Timeout check
            if manager.check_timeout(game_id):
                if game["winner"] is None:
                    scores = game["scores"]

                    if scores[0] > scores[1]:
                        game["winner"] = 0
                    elif scores[1] > scores[0]:
                        game["winner"] = 1
                    else:
                        game["winner"] = "draw"

                # Broadcast to all players
                for player in game["players"]:
                    await player.send_text(json.dumps({
                        "type": "game_over",
                        "reason": "time_up",
                        "winner": game["winner"],
                        "scores": game["scores"]
                    }))
                continue

            # Handle moves
            if message["type"] == "move":

                print("TURN BEFORE:", game["turn"])
                print("PLAYER:", player_id)

                success, msg = manager.apply_move(game_id, row, col, value)

                print("SUCCESS:", success)

                if success:
                    game["turn"] = 1 - game["turn"]

                print("TURN AFTER:", game["turn"])

                row = message["row"]
                col = message["col"]
                value = message["value"]

                success, msg = manager.apply_move(game_id, row, col, value)

                if success:
                    # Update score
                    game["scores"][player_id] += 1

                    # Switch turn
                    game["turn"] = 1 - game["turn"]

                    # Check win condition (full board)
                    if manager.check_win(game_id):
                        game["winner"] = player_id

                response = {
                    "type": "update",
                    "success": success,
                    "message": msg,
                    "board": game["board"],
                    "turn": game["turn"],
                    "scores": game["scores"],
                    "time_left": manager.get_time_left(game_id),
                    "game_over": game["winner"] is not None,
                    "winner": game["winner"]
                }

                # Broadcast update
                for player in game["players"]:
                    await player.send_text(json.dumps(response))

    except WebSocketDisconnect:
        game["players"].remove(websocket)


@app.post("/create")
def create_game():
    game_id = manager.create_game()
    return {"game_id": game_id}