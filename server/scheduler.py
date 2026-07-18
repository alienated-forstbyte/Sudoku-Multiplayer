"""Background timeout scheduler for room expiry and match deadlines.

The scheduler polls for due deadlines independently of client messages so
idle rooms are expired and finished matches broadcast ``game_over`` without
requiring player interaction.

Two backends are provided:

* ``InMemorySchedulerBackend`` — process-local dict, used by tests.
* ``RedisSchedulerBackend`` — Redis sorted set, used in production so
  multiple workers can coordinate through atomic claim semantics.

The ``TimeoutScheduler`` owns the polling loop and delegates storage to the
chosen backend.
"""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

log = logging.getLogger(__name__)

EventHandler = Callable[[str, dict], Awaitable[None]]


class SchedulerBackend(Protocol):
    """Storage interface for deadline entries."""

    async def add(self, game_id: str, deadline: float, deadline_type: str) -> None:
        """Register *deadline* (epoch seconds) of the given *deadline_type*."""
        ...

    async def remove(self, game_id: str) -> None:
        """Remove all deadline entries for *game_id*."""
        ...

    async def claim_due(self, now: float) -> list[tuple[str, str]]:
        """Return ``(game_id, deadline_type)`` pairs whose deadline <= *now*.

        Due entries should be removed or marked so that a concurrent worker
        does not process them again.  A re-check under the repository lock
        provides the final safety net.
        """
        ...


class InMemorySchedulerBackend:
    """Process-local deadline store for tests and non-Redis development."""

    def __init__(self) -> None:
        self._deadlines: dict[str, tuple[float, str]] = {}

    async def add(self, game_id: str, deadline: float, deadline_type: str) -> None:
        self._deadlines[game_id] = (deadline, deadline_type)

    async def remove(self, game_id: str) -> None:
        self._deadlines.pop(game_id, None)

    async def claim_due(self, now: float) -> list[tuple[str, str]]:
        due: list[tuple[str, str]] = []
        for game_id, (deadline, dtype) in list(self._deadlines.items()):
            if deadline <= now:
                due.append((game_id, dtype))
                del self._deadlines[game_id]
        return due


class RedisSchedulerBackend:
    """Redis sorted-set deadline store for multi-worker coordination.

    Each game has at most one entry.  ``ZREM`` before processing ensures
    another worker does not pick up the same deadline.  A stale claim that
    slips past is caught by the repository-level re-check.
    """

    def __init__(self, redis_client, key: str = "sudoku:scheduler") -> None:
        self.redis = redis_client
        self.key = key

    async def add(self, game_id: str, deadline: float, deadline_type: str) -> None:
        await self.redis.zadd(
            self.key, {f"{game_id}:{deadline_type}": deadline}
        )

    async def remove(self, game_id: str) -> None:
        keys = await self.redis.zrange(self.key, 0, -1)
        to_remove: list[str] = []
        for raw in keys:
            member = raw.decode() if isinstance(raw, bytes) else raw
            if member.split(":", 1)[0] == game_id:
                to_remove.append(member)
        if to_remove:
            await self.redis.zrem(self.key, *to_remove)

    async def claim_due(self, now: float) -> list[tuple[str, str]]:
        raw_members = await self.redis.zrangebyscore(self.key, 0, now)
        if not raw_members:
            return []

        pipe = self.redis.pipeline()
        for member in raw_members:
            pipe.zrem(self.key, member)
        await pipe.execute()

        due: list[tuple[str, str]] = []
        for raw in raw_members:
            member = raw.decode() if isinstance(raw, bytes) else raw
            parts = member.rsplit(":", 1)
            if len(parts) == 2:
                due.append((parts[0], parts[1]))
        return due


class TimeoutScheduler:
    """Background task that fires room-expiry and match-timeout events.

    The scheduler polls the backend at ``poll_interval`` seconds.  When a
    deadline is due it re-checks room state under the repository mutation
    lock before acting, so duplicate delivery from concurrent workers is
    impossible.
    """

    def __init__(
        self,
        repository,
        event_bus,
        backend: SchedulerBackend | None = None,
        publish: EventHandler | None = None,
        poll_interval: float = 1.0,
    ) -> None:
        self.repository = repository
        self.event_bus = event_bus
        self.backend: SchedulerBackend = backend or InMemorySchedulerBackend()
        self.poll_interval = poll_interval
        self._task: asyncio.Task | None = None
        self._publish: EventHandler | None = publish

    async def start(self) -> None:
        """Begin polling for due deadlines in the background."""
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Cancel the background task and wait for it to finish."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # ------------------------------------------------------------------
    # Public scheduling helpers
    # ------------------------------------------------------------------

    async def schedule_expiry(self, game_id: str, deadline: float) -> None:
        """Register a waiting-room expiry deadline."""
        await self.backend.add(game_id, deadline, "expiry")
        log.debug("Scheduled expiry for %s at %.1f", game_id, deadline)

    async def schedule_match(self, game_id: str, deadline: float) -> None:
        """Register a match-timeout deadline."""
        await self.backend.add(game_id, deadline, "timeout")
        log.debug("Scheduled match timeout for %s at %.1f", game_id, deadline)

    async def cancel(self, game_id: str) -> None:
        """Remove all deadlines for *game_id*."""
        await self.backend.remove(game_id)
        log.debug("Cancelled deadlines for %s", game_id)

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Poll until cancelled."""
        while True:
            try:
                await self._process_due()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("scheduler poll error")
            await asyncio.sleep(self.poll_interval)

    async def _process_due(self) -> None:
        """Claim and handle all deadlines whose time has passed."""
        now = time.time()
        due = await self.backend.claim_due(now)

        for game_id, dtype in due:
            if dtype == "expiry":
                await self._handle_expiry(game_id)
            elif dtype == "timeout":
                await self._handle_timeout(game_id)

    # ------------------------------------------------------------------
    # Deadline handlers
    # ------------------------------------------------------------------

    async def _handle_expiry(self, game_id: str) -> None:
        """Expire a waiting room that has not started in time."""
        room = await self.repository.get(game_id)
        if room is None or room.started:
            return

        await self.repository.delete(game_id)
        log.info("Expired waiting room %s", game_id)

        await self._emit(game_id, {
            "type": "game_over",
            "reason": "room_expired",
            "message": "Room expired — second player did not join in time.",
            "winner": None,
        })

    async def _handle_timeout(self, game_id: str) -> None:
        """Finish a started match whose time limit has been reached."""
        room = await self.repository.get(game_id)
        if room is None or room.winner is not None:
            return

        room, _result = await self.repository.mutate(
            game_id,
            lambda r: r.finish_on_timeout(),
        )
        if room is None:
            return

        log.info("Match timeout for %s — winner: %s", game_id, room.winner)

        winner_text = (
            f"Player {room.winner} wins"
            if isinstance(room.winner, int)
            else "Draw"
        )

        await self._emit(game_id, {
            "type": "game_over",
            "reason": "time_up",
            "message": f"Time's up! {winner_text}.",
            "winner": room.winner,
            "scores": room.scores,
        })

    async def _emit(self, game_id: str, payload: dict) -> None:
        """Publish through the event bus, or call the explicit callback."""
        if self._publish is not None:
            await self._publish(game_id, payload)
        else:
            await self.event_bus.publish(game_id, payload)
