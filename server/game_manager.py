import uuid
from engine.generator import generate_full_board, remove_numbers


class GameManager:
    def __init__(self):
        self.games = {}  # game_id -> game data

    def create_game(self):
        game_id = str(uuid.uuid4())

        full = generate_full_board()
        puzzle = remove_numbers(full, "medium")

        self.games[game_id] = {
            "players": [],
            "board": puzzle,
        }

        return game_id

    def join_game(self, game_id, websocket):
        if game_id not in self.games:
            return False

        self.games[game_id]["players"].append(websocket)
        return True

    def get_game(self, game_id):
        return self.games.get(game_id)