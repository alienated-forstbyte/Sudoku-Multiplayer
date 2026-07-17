import uuid
import time
import random
import json
import httpx
from engine.generator import generate_full_board, remove_numbers
from server.config import Settings, load_settings
from server.events import InMemoryEventBus
from server.models import RoomState, freeze_board
from server.repository import InMemoryRoomRepository


class GameManager:
    """Coordinate shared rooms, local sockets, and supporting services.

    The repository owns serializable state; the event bus carries protocol
    events between workers. Only live WebSocket objects remain process-local.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
        repository=None,
        event_bus=None,
    ):
        self.settings = settings or load_settings()
        self.http_client = http_client
        self.repository = repository or InMemoryRoomRepository()
        self.event_bus = event_bus or InMemoryEventBus()
        self.local_connections: dict[str, dict[int, object]] = {}

    async def start(self) -> None:
        await self.event_bus.start(self._deliver_local)

    async def stop(self) -> None:
        for game_id, connections in list(self.local_connections.items()):
            player_ids = tuple(connections)

            def release_local_players(room, ids=player_ids):
                for player_id in ids:
                    room.remove_player(player_id)

            await self.repository.mutate(game_id, release_local_players)
        await self.event_bus.stop()
        self.local_connections.clear()

    async def _deliver_local(self, game_id: str, payload: dict) -> None:
        """Forward one shared event to sockets connected to this worker."""
        connections = self.local_connections.get(game_id, {})
        stale_ids = []
        message = json.dumps(payload)
        for player_id, connection in list(connections.items()):
            try:
                await connection.send_text(message)
            except Exception:
                stale_ids.append(player_id)

        for player_id in stale_ids:
            connections.pop(player_id, None)

    async def broadcast(self, game_id: str, payload: dict) -> None:
        await self.event_bus.publish(game_id, payload)

    async def is_expired(self, game_id):
        game = await self.repository.get(game_id)
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

        room = RoomState(
            created_at=time.time(),
            expiry_seconds=self.settings.room_expiry_seconds,
            board=puzzle,
            original_board=original_board,
            solution=full,
            difficulty=predicted_difficulty,
            puzzle_hash=puzzle_hash,
            time_limit_seconds=self.settings.game_time_limit_seconds,
        )
        await self.repository.create(game_id, room)

        return game_id

    async def join_game(self, game_id, websocket):
        """Reserve a shared player ID and register its socket on this worker.

        Returns ``(player_id, room, started_now)``. The repository mutation is
        atomic, so two workers cannot reserve the same final slot.
        """
        game = await self.repository.get(game_id)
        if game is None:
            return None, None, False
        if game.is_expired():
            await self.repository.delete(game_id)
            return None, None, False

        def reserve_player(room):
            was_started = room.started
            player_id = room.add_player()
            return player_id, not was_started and room.started

        game, result = await self.repository.mutate(
            game_id,
            reserve_player,
        )
        if game is None or result is None:
            return None, None, False

        player_id, started_now = result
        if player_id is None:
            return None, game, False

        self.local_connections.setdefault(game_id, {})[player_id] = websocket
        return player_id, game, started_now

    async def disconnect(self, game_id: str, player_id: int) -> None:
        connections = self.local_connections.get(game_id)
        if connections:
            connections.pop(player_id, None)
            if not connections:
                self.local_connections.pop(game_id, None)
        await self.repository.mutate(
            game_id,
            lambda room: room.remove_player(player_id),
        )

    async def get_game(self, game_id):
        return await self.repository.get(game_id)
    
    async def verify_puzzle(self, game_id):
        """Ask the hash-chain service whether the original puzzle is authentic.

        Verification always uses ``original_board``, never the live shared
        board, so accepted moves do not invalidate integrity checks.
        """
        game = await self.repository.get(game_id)
        if game is None:
            return False

        response = await self._require_http_client().post(
            self.settings.blockchain_verify_url,
            json={
                "data": json.dumps(game.original_board),
                "hash": game.puzzle_hash,
            },
        )
        response.raise_for_status()

        return response.json()["valid"]
    
    async def apply_move(self, game_id, player_id, row, col, value):
        game, result = await self.repository.mutate(
            game_id,
            lambda room: room.apply_move(player_id, row, col, value),
        )
        if game is None:
            return None, False, "Game not found"
        success, message = result
        return game, success, message

    async def get_time_left(self, game_id):
        game = await self.repository.get(game_id)
        if not game:
            return 0

        return game.time_left()

    async def check_timeout(self, game_id):
        return await self.get_time_left(game_id) <= 0

    async def finish_on_timeout(self, game_id):
        return await self.repository.mutate(
            game_id,
            lambda room: room.finish_on_timeout(),
        )

    async def check_win_player(self, game_id, _player_id):
        """Return completion for the room's shared board."""
        room = await self.repository.get(game_id)
        return room.is_complete() if room else False