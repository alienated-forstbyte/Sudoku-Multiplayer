import uuid
import time
import random
import json
from ml.predict import predict_difficulty
from engine.generator import generate_full_board, remove_numbers
from blockchain.ledger import Blockchain


class GameManager:
    def __init__(self):
        self.games = {}  # game_id -> game data
        self.blockchain = Blockchain()



    def create_game(self):
        game_id = str(uuid.uuid4())

        self.games[game_id] = {
            "players": [],
            "boards": {},
            "solutions": {},
            "scores": {},
            "difficulties": {},
            "hashes": {},
            "start_time": None,
            "time_limit": 600,
            "started": False,
            "winner": None
        }

        return game_id

    def join_game(self, game_id, websocket):
        if game_id not in self.games:
            return None

        game = self.games[game_id]

        if len(game["players"]) >= 2:
            return None

        game["players"].append(websocket)
        player_id = len(game["players"]) - 1

        # Generate board for this player
        full = generate_full_board()
        puzzle = remove_numbers(full, random.choice(["easy","medium","hard"]))

        # store first
        game["boards"][player_id] = puzzle
        game["solutions"][player_id] = full
        game["scores"][player_id] = 0

        # ML
        predicted_difficulty = predict_difficulty(puzzle)
        game["difficulties"][player_id] = predicted_difficulty

        # Blockchain (last)
        puzzle_hash = self.blockchain.add_block(json.dumps(puzzle, sort_keys=True))
        game["hashes"][player_id] = puzzle_hash

        # Start game when 2 players join
        if len(game["players"]) == 2:
            game["started"] = True
            game["start_time"] = time.time()

        return player_id

    def get_game(self, game_id):
        return self.games.get(game_id)
    
    def verify_puzzle(self, game_id, player_id):
        game = self.games[game_id]

        puzzle = game["boards"][player_id]
        stored_hash = game["hashes"][player_id]

        current_hash = self.blockchain.chain[-1].compute_hash()

        return self.blockchain.verify(
            json.dumps(puzzle, sort_keys=True),
            stored_hash
        )
    
    def apply_move(self, game_id, player_id, row, col, value):
        game = self.games.get(game_id)
        if not game:
            return False, "Game not found"

        board = game["boards"][player_id]
        solution = game["solutions"][player_id]

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