import uuid
import time
import random
import json
import httpx
from engine.generator import generate_full_board, remove_numbers
from server.config import Settings, load_settings


class GameManager:
    """Own process-local rooms and coordinate the supporting services.

    Room state is intentionally kept in a dictionary for this prototype. It is
    lost on restart and cannot be shared by multiple server workers.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings or load_settings()
        self.http_client = http_client
        self.games = {}  # game_id -> game data

    def is_expired(self, game_id):
        game = self.games.get(game_id)
        if not game:
            return True

        if game["started"]:
            return False

        return (time.time() - game["created_at"]) > game["expiry"]

    def _require_http_client(self) -> httpx.AsyncClient:
        if self.http_client is None:
            raise RuntimeError("GameManager HTTP client is not initialized")
        return self.http_client

    async def create_game(self):
        """Generate a puzzle, classify and hash it, then store a new room.

        The two required service calls use the process-wide async HTTP client.
        An unavailable ML or hash-chain service causes room creation to fail
        within the configured connect/read timeout.
        """
        full = generate_full_board()
        difficulty = random.choice(["easy", "medium", "hard"])
        puzzle = remove_numbers(full, difficulty)

        # The generated label chooses clue count; the model supplies the label
        # shown to players.
        response = await self._require_http_client().post(
            self.settings.predict_url,
            json={"board": puzzle},
        )
        response.raise_for_status()
        predicted_difficulty = response.json()["difficulty"]

        # Hash the immutable original puzzle; live ``board`` may change later.
        original_board = [row[:] for row in puzzle]
        response = await self._require_http_client().post(
            self.settings.blockchain_add_url,
            json={"data": json.dumps(original_board)},
        )
        response.raise_for_status()

        puzzle_hash = response.json()["hash"]

        game_id = str(uuid.uuid4())

        self.games[game_id] = {
            "created_at": time.time(),
            "expiry": self.settings.room_expiry_seconds,

            "players": [],

            "board": puzzle,
            "original_board": original_board,
            "solution": full,
            "difficulty": predicted_difficulty,
            "hash": puzzle_hash,

            "scores": {0: 0, 1: 0},

            "start_time": None,
            "time_limit": self.settings.game_time_limit_seconds,
            "started": False,
            "winner": None
        }

        return game_id

    def join_game(self, game_id, websocket):
        """Add one connection and return its player ID, or ``None``.

        Player IDs currently match indexes in ``players``. Removing a
        disconnected socket can therefore make reconnect behavior ambiguous;
        persistent player records would be safer in a production protocol.
        """
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
    
    async def verify_puzzle(self, game_id):
        """Ask the hash-chain service whether the original puzzle is authentic.

        Verification always uses ``original_board``, never the live shared
        board, so accepted moves do not invalidate integrity checks.
        """
        game = self.games[game_id]

        response = await self._require_http_client().post(
            self.settings.blockchain_verify_url,
            json={
                "data": json.dumps(game["original_board"]),
                "hash": game["hash"]
            },
        )
        response.raise_for_status()

        return response.json()["valid"]
    
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