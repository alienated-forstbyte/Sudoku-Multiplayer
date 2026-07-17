import uuid
import time
import random
import json
import httpx
from engine.generator import generate_full_board, remove_numbers
from server.config import Settings, load_settings
from server.models import RoomState, freeze_board


class GameManager:
    """Own process-local rooms and coordinate the supporting services.

    Room state is typed but remains process-local. It is lost on restart and
    cannot be shared by multiple server workers.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.settings = settings or load_settings()
        self.http_client = http_client
        self.games: dict[str, RoomState] = {}

    def is_expired(self, game_id):
        game = self.games.get(game_id)
        if not game:
            return True

        return game.is_expired()

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
        original_board = freeze_board(puzzle)
        response = await self._require_http_client().post(
            self.settings.blockchain_add_url,
            json={"data": json.dumps(original_board)},
        )
        response.raise_for_status()

        puzzle_hash = response.json()["hash"]

        game_id = str(uuid.uuid4())

        self.games[game_id] = RoomState(
            created_at=time.time(),
            expiry_seconds=self.settings.room_expiry_seconds,
            board=puzzle,
            original_board=original_board,
            solution=full,
            difficulty=predicted_difficulty,
            puzzle_hash=puzzle_hash,
            time_limit_seconds=self.settings.game_time_limit_seconds,
        )

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

        return game.add_player(websocket)

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
                "data": json.dumps(game.original_board),
                "hash": game.puzzle_hash,
            },
        )
        response.raise_for_status()

        return response.json()["valid"]
    
    def apply_move(self, game_id, player_id, row, col, value):
        game = self.games.get(game_id)
        if not game:
            return False, "Game not found"

        return game.apply_move(player_id, row, col, value)
    
    def get_time_left(self, game_id):
        game = self.games.get(game_id)
        if not game:
            return 0

        return game.time_left()
    
    def check_timeout(self, game_id):
        return self.get_time_left(game_id) <= 0
    
    def check_win_player(self, game_id, _player_id):
        """Return completion for the room's shared board."""
        return self.games[game_id].is_complete()