"""Room event buses for local tests and Redis-backed multi-worker delivery."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import suppress

import structlog

log = structlog.get_logger(__name__)

EventHandler = Callable[[str, dict], Awaitable[None]]


class InMemoryEventBus:
    def __init__(self):
        self._handlers: list[EventHandler] = []

    async def start(self, handler: EventHandler) -> None:
        if handler not in self._handlers:
            self._handlers.append(handler)

    async def stop(self) -> None:
        self._handlers.clear()

    async def publish(self, game_id: str, payload: dict) -> None:
        for handler in list(self._handlers):
            await handler(game_id, payload)


class RedisEventBus:
    """Publish room events and consume them in every game-server worker."""

    def __init__(self, redis_client, channel_prefix="sudoku:events:"):
        self.redis = redis_client
        self.channel_prefix = channel_prefix
        self._pubsub = None
        self._task: asyncio.Task | None = None

    async def start(self, handler: EventHandler) -> None:
        self._pubsub = self.redis.pubsub()
        await self._pubsub.psubscribe(f"{self.channel_prefix}*")
        self._task = asyncio.create_task(self._listen(handler))
        log.info("event_bus.started", prefix=self.channel_prefix)

    async def _listen(self, handler: EventHandler) -> None:
        async for message in self._pubsub.listen():
            if message["type"] != "pmessage":
                continue
            channel = message["channel"]
            data = message["data"]
            if isinstance(channel, bytes):
                channel = channel.decode()
            if isinstance(data, bytes):
                data = data.decode()
            game_id = channel.removeprefix(self.channel_prefix)
            try:
                await handler(game_id, json.loads(data))
            except Exception:
                log.exception(
                    "event_bus.handler_error", game_id=game_id
                )

    async def publish(self, game_id: str, payload: dict) -> None:
        await self.redis.publish(
            f"{self.channel_prefix}{game_id}",
            json.dumps(payload),
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._pubsub:
            await self._pubsub.aclose()
            self._pubsub = None
        log.info("event_bus.stopped")
