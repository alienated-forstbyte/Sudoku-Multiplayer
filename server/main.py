from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from server.game_manager import GameManager
import json

app = FastAPI()
manager = GameManager()


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    await websocket.accept()

    # Join or reject
    if not manager.join_game(game_id, websocket):
        await websocket.send_text("Invalid game ID")
        await websocket.close()
        return

    game = manager.get_game(game_id)

    # Send initial board
    await websocket.send_text(json.dumps({
        "type": "init",
        "board": game["board"]
    }))

    try:
        while True:
            data = await websocket.receive_text()

            # Broadcast to players in same game
            for player in game["players"]:
                await player.send_text(data)

    except WebSocketDisconnect:
        game["players"].remove(websocket)

@app.post("/create")
def create_game():
    game_id = manager.create_game()
    return {"game_id": game_id}