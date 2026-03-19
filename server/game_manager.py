import uuid
from engine.generator import generate_full_board, remove_numbers
import time


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
            "solution": full,
            "turn": 0,
            "winner": None,
            "scores": {0: 0, 1: 0},

            # ⏱ Timer
            "start_time": time.time(),
            "time_limit": 600  # 10 minutes in seconds
        }

        return game_id

    def join_game(self, game_id, websocket):
        if game_id not in self.games:
            return None

        game = self.games[game_id]

        if len(game["players"]) == 2:
            game["start_time"] = time.time()

        game["players"].append(websocket)
        player_id = len(game["players"]) - 1

        return player_id

    def get_game(self, game_id):
        return self.games.get(game_id)
    
    def apply_move(self, game_id, row, col, value):
        game = self.games.get(game_id)
        if not game:
            return False, "Game not found"

        board = game["board"]
        solution = game["solution"]

        # Prevent overwriting filled cells
        if board[row][col] != 0:
            return False, "Cell already filled"

        # Check against solution
        if solution[row][col] != value:
            return False, "Incorrect move"

        # Apply move
        board[row][col] = value
        return True, "Move accepted"
    
    def get_time_left(self, game_id):
        game = self.games.get(game_id)
        if not game:
            return 0

        elapsed = time.time() - game["start_time"]
        remaining = game["time_limit"] - elapsed

        return max(0, int(remaining))
    
    def check_timeout(self, game_id):
        return self.get_time_left(game_id) <= 0