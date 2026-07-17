"""Room persistence backends with atomic mutation boundaries."""

import asyncio
import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any, Protocol

from server.models import RoomState


Mutation = Callable[[RoomState], Any]


class RoomRepository(Protocol):
    async def create(self, game_id: str, room: RoomState) -> None: ...

    async def get(self, game_id: str) -> RoomState | None: ...

    async def delete(self, game_id: str) -> None: ...

    async def mutate(
        self,
        game_id: str,
        mutation: Mutation,
    ) -> tuple[RoomState | None, Any]: ...


class InMemoryRoomRepository:
    """Process-local repository used by tests and non-Redis development."""

    def __init__(self):
        self._rooms: dict[str, RoomState] = {}
        self._lock = asyncio.Lock()

    async def create(self, game_id: str, room: RoomState) -> None:
        async with self._lock:
            self._rooms[game_id] = deepcopy(room)

    async def get(self, game_id: str) -> RoomState | None:
        async with self._lock:
            room = self._rooms.get(game_id)
            return deepcopy(room) if room else None

    async def delete(self, game_id: str) -> None:
        async with self._lock:
            self._rooms.pop(game_id, None)

    async def mutate(
        self,
        game_id: str,
        mutation: Mutation,
    ) -> tuple[RoomState | None, Any]:
        async with self._lock:
            room = self._rooms.get(game_id)
            if room is None:
                return None, None
            result = mutation(room)
            return deepcopy(room), result

    async def clear(self) -> None:
        async with self._lock:
            self._rooms.clear()


class RedisRoomRepository:
    """Redis-backed room snapshots serialized as JSON.

    A per-room distributed lock makes each read-modify-write mutation atomic
    across game-server workers.
    """

    def __init__(
        self,
        redis_client,
        ttl_seconds: int,
        key_prefix: str = "sudoku:room:",
    ):
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix

    def _key(self, game_id: str) -> str:
        return f"{self.key_prefix}{game_id}"

    def _lock_key(self, game_id: str) -> str:
        return f"{self._key(game_id)}:lock"

    async def create(self, game_id: str, room: RoomState) -> None:
        await self.redis.set(
            self._key(game_id),
            json.dumps(room.to_dict()),
            ex=self.ttl_seconds,
        )

    async def get(self, game_id: str) -> RoomState | None:
        raw = await self.redis.get(self._key(game_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return RoomState.from_dict(json.loads(raw))

    async def delete(self, game_id: str) -> None:
        await self.redis.delete(self._key(game_id))

    async def mutate(
        self,
        game_id: str,
        mutation: Mutation,
    ) -> tuple[RoomState | None, Any]:
        lock = self.redis.lock(
            self._lock_key(game_id),
            timeout=10,
            blocking_timeout=5,
        )
        async with lock:
            room = await self.get(game_id)
            if room is None:
                return None, None
            result = mutation(room)
            await self.create(game_id, room)
            return room, result
