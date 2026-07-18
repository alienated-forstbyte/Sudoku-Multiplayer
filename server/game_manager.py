"""Coordinate shared rooms, local sockets, and supporting services.

Manages the lifecycle of game rooms: creation (with puzzle generation, ML
classification, and blockchain hashing), player joining, move processing,
verification, and broadcasting.  Designed for multi-worker deployment with
a pluggable repository and event bus.
"""

import json
import random
import time
import uuid

import httpx
import structlog

from engine.generator import generate_full_board, remove_numbers
from server.config import Settings, load_settings
from server.events import InMemoryEventBus
from server.models import RoomState, freeze_board
from server.repository import InMemoryRoomRepository

log = structlog.get_logger(__name__)


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
        scheduler=None,
    ):
        self.settings = settings or load_settings()
        self.http_client = http_client
        self.repository = repository or InMemoryRoomRepository()
        self.event_bus = event_bus or InMemoryEventBus()
        self.local_connections: dict[str, dict[int, object]] = {}
        self.scheduler = scheduler
        self._redis_client = None

    async def start(self) -> None:
        await self.event_bus.start(self._deliver_local)

    async def stop(self) -> None:
        if self.scheduler is not None:
            await self.scheduler.stop()
        for game_id, connections in list(self.local_connections.items()):
            player_ids = tuple(connections)

            def release_local_players(room, ids=player_ids):
                for player_id in ids:
                    room.remove_player(player_id)

            await self.repository.mutate(game_id, release_local_players)
        await self.event_bus.stop()
        self.local_connections.clear()

    def set_redis_client(self, redis_client) -> None:
        """Store the Redis client so the health endpoint can ping it."""
        self._redis_client = redis_client

    async def redis_ping(self) -> bool:
        """Return True if the Redis connection is alive."""
        if self._redis_client is None:
            return True
        try:
            return await self._redis_client.ping()
        except Exception:
            return False

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

        Service failures are handled gracefully when
        ``settings.allow_degraded_creation`` is True: the ML label falls back
        to the local difficulty, and the blockchain hash becomes an empty
        string.
        """
        full = generate_full_board()
        difficulty = random.choice(["easy", "medium", "hard"])
        puzzle = remove_numbers(full, difficulty)

        predicted_difficulty = difficulty

        try:
            response = await self._require_http_client().post(
                self.settings.predict_url,
                json={"board": puzzle},
            )
            response.raise_for_status()
            predicted_difficulty = response.json()["difficulty"]
        except Exception:
            if self.settings.allow_degraded_creation:
                log.warning(
                    "ml_service.unavailable",
                    fallback_difficulty=difficulty,
                )
            else:
                raise

        original_board = freeze_board(puzzle)
        puzzle_hash = ""

        try:
            response = await self._require_http_client().post(
                self.settings.blockchain_add_url,
                json={"data": json.dumps(original_board)},
            )
            response.raise_for_status()
            puzzle_hash = response.json()["hash"]
        except Exception:
            if self.settings.allow_degraded_creation:
                log.warning("blockchain_service.unavailable")
            else:
                raise

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

        if self.scheduler is not None:
            await self.scheduler.schedule_expiry(
                game_id, room.created_at + room.expiry_seconds
            )

        log.info(
            "game.room_created",
            game_id=game_id,
            difficulty=predicted_difficulty,
            degraded=puzzle_hash == "",
        )
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

        if started_now and self.scheduler is not None:
            await self.scheduler.cancel(game_id)
            deadline = game.start_time + game.time_limit_seconds
            await self.scheduler.schedule_match(game_id, deadline)
            log.info("game.match_started", game_id=game_id)

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
        log.info("player.disconnected", game_id=game_id, player_id=player_id)

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
        if success and game.winner is not None and self.scheduler is not None:
            await self.scheduler.cancel(game_id)
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
