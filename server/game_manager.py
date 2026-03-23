import uuid
import time
import random
import json
import requests
from ml.predict import predict_difficulty
from engine.generator import generate_full_board, remove_numbers
from blockchain.ledger import Blockchain

# game = {
#     "board": ONE shared board,
#     "solution": ONE solution,
#     "difficulty": ONE value,
#     "hash": ONE hash,
#     "players": [],
#     "scores": {},
# }

class GameManager:
    def __init__(self):
        self.games = {}  # game_id -> game data
        self.blockchain = Blockchain()

    def is_expired(self, game_id):
        game = self.games.get(game_id)
        if not game:
            return True

        if game["started"]:
            return False

        return (time.time() - game["created_at"]) > game["expiry"]

    def create_game(self):
        full = generate_full_board()
        difficulty = random.choice(["easy", "medium", "hard"])
        puzzle = remove_numbers(full, difficulty)

        # ML (optional)
        response = requests.post(
            "http://ml_service:8001/predict",
            json={"board": puzzle}
        )
        predicted_difficulty = response.json()["difficulty"]

        # Blockchain
        puzzle_hash = self.blockchain.add_block(
            json.dumps(puzzle, sort_keys=True)
        )

        game_id = str(uuid.uuid4())

        self.games[game_id] = {
            "created_at": time.time(),
            "expiry": 25,

            "players": [],

            "board": puzzle,
            "solution": full,
            "difficulty": predicted_difficulty,
            "hash": puzzle_hash,

            "scores": {0: 0, 1: 0},

            "start_time": None,
            "time_limit": 600,
            "started": False,
            "winner": None
        }

        return game_id

    def join_game(self, game_id, websocket):
        if game_id not in self.games:
            return None

        if self.is_expired(game_id):
            del self.games[game_id]
            return None

        game = self.games[game_id]

        if len(game["players"]) >= 2:
            return None

        game["players"].append(websocket)
        player_id = len(game["players"]) - 1

        game["scores"][player_id] = 0

        if len(game["players"]) == 2:
            game["started"] = True
            game["start_time"] = time.time()

        return player_id

    def get_game(self, game_id):
        return self.games.get(game_id)
    
    def verify_puzzle(self, game_id):
        game = self.games[game_id]

        return self.blockchain.verify(
            json.dumps(game["board"], sort_keys=True),
            game["hash"]
        )
    
    def apply_move(self, game_id, player_id, row, col, value):
        game = self.games.get(game_id)
        if not game:
            return False, "Game not found"

        board = game["board"]
        solution = game["solution"]

        if board[row][col] != 0:
            return False, "Cell already filled"

        if solution[row][col] != value:
            return False, "Incorrect move"

        board[row][col] = value
        game["scores"][player_id] += 1

        return True, "Correct move"
    
    def get_time_left(self, game_id):
        game = self.games.get(game_id)
        if not game:
            return 0

        if game["start_time"] is None:
            return game["time_limit"]

        elapsed = time.time() - game["start_time"]
        remaining = game["time_limit"] - elapsed

        return max(0, int(remaining))
    
    def check_timeout(self, game_id):
        return self.get_time_left(game_id) <= 0
    
    def check_win_player(self, game_id, player_id):
        board = self.games[game_id]["boards"][player_id]
        return all(0 not in row for row in board)