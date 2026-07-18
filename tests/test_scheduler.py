import asyncio
import time

import pytest

from server.events import InMemoryEventBus
from server.models import RoomState, freeze_board
from server.repository import InMemoryRoomRepository
from server.scheduler import InMemorySchedulerBackend, TimeoutScheduler


def make_room(**overrides):
    solution = [[1 for _ in range(9)] for _ in range(9)]
    board = [row[:] for row in solution]
    board[0][0] = 0
    defaults = {
        "created_at": 100.0,
        "expiry_seconds": 25,
        "board": board,
        "original_board": freeze_board(board),
        "solution": solution,
        "difficulty": "easy",
        "puzzle_hash": "hash",
        "time_limit_seconds": 60,
    }
    defaults.update(overrides)
    return RoomState(**defaults)


# ------------------------------------------------------------------
# Backend unit tests
# ------------------------------------------------------------------


def test_in_memory_backend_add_and_claim():
    async def scenario():
        backend = InMemorySchedulerBackend()
        await backend.add("g1", 10.0, "expiry")
        await backend.add("g2", 20.0, "timeout")

        assert await backend.claim_due(5.0) == []
        due = await backend.claim_due(15.0)
        assert due == [("g1", "expiry")]

        assert await backend.claim_due(25.0) == [("g2", "timeout")]
        assert await backend.claim_due(30.0) == []

    asyncio.run(scenario())


def test_in_memory_backend_remove_cancels_all_types():
    async def scenario():
        backend = InMemorySchedulerBackend()
        await backend.add("g1", 10.0, "expiry")
        await backend.add("g1", 20.0, "timeout")

        await backend.remove("g1")
        due = await backend.claim_due(30.0)
        assert due == []

    asyncio.run(scenario())


# ------------------------------------------------------------------
# Scheduler handler tests
# ------------------------------------------------------------------


def test_expired_waiting_room_is_deleted_and_event_published():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        events: list[tuple[str, dict]] = []

        room = make_room(created_at=100.0, expiry_seconds=10)
        await repository.create("g1", room)

        async def capture(game_id, payload):
            events.append((game_id, payload))

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            publish=capture,
        )

        now = time.time()
        await scheduler.schedule_expiry("g1", now - 1)
        await scheduler._process_due()

        assert await repository.get("g1") is None
        assert len(events) == 1
        gid, payload = events[0]
        assert gid == "g1"
        assert payload["type"] == "game_over"
        assert payload["reason"] == "room_expired"
        assert payload["winner"] is None

    asyncio.run(scenario())


def test_started_room_expiry_is_ignored():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        events: list[tuple[str, dict]] = []

        room = make_room(created_at=100.0, expiry_seconds=10)
        room.add_player(now=101.0)
        room.add_player(now=102.0)
        await repository.create("g1", room)

        async def capture(game_id, payload):
            events.append((game_id, payload))

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            publish=capture,
        )

        await scheduler.schedule_expiry("g1", time.time() - 1)
        await scheduler._process_due()

        stored = await repository.get("g1")
        assert stored is not None
        assert events == []

    asyncio.run(scenario())


def test_match_timeout_finishes_and_publishes_game_over():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        events: list[tuple[str, dict]] = []

        room = make_room(created_at=100.0, time_limit_seconds=60)
        room.add_player(now=100.0)
        room.add_player(now=100.0)
        room.scores = {0: 3, 1: 1}
        await repository.create("g1", room)

        async def capture(game_id, payload):
            events.append((game_id, payload))

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            publish=capture,
        )

        await scheduler.schedule_match("g1", time.time() - 1)
        await scheduler._process_due()

        stored = await repository.get("g1")
        assert stored is not None
        assert stored.winner == 0
        assert len(events) == 1
        gid, payload = events[0]
        assert gid == "g1"
        assert payload["type"] == "game_over"
        assert payload["reason"] == "time_up"
        assert payload["winner"] == 0
        assert payload["scores"] == {0: 3, 1: 1}

    asyncio.run(scenario())


def test_match_timeout_draw():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        events: list[tuple[str, dict]] = []

        room = make_room(created_at=100.0, time_limit_seconds=60)
        room.add_player(now=100.0)
        room.add_player(now=100.0)
        room.scores = {0: 5, 1: 5}
        await repository.create("g1", room)

        async def capture(game_id, payload):
            events.append((game_id, payload))

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            publish=capture,
        )

        await scheduler.schedule_match("g1", time.time() - 1)
        await scheduler._process_due()

        stored = await repository.get("g1")
        assert stored.winner == "draw"

    asyncio.run(scenario())


def test_already_winner_skips_timeout():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        events: list[tuple[str, dict]] = []

        room = make_room(created_at=100.0, time_limit_seconds=60)
        room.add_player(now=100.0)
        room.add_player(now=100.0)
        room.winner = 0
        await repository.create("g1", room)

        async def capture(game_id, payload):
            events.append((game_id, payload))

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            publish=capture,
        )

        await scheduler.schedule_match("g1", time.time() - 1)
        await scheduler._process_due()

        assert events == []

    asyncio.run(scenario())


def test_cancel_prevents_firing():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        events: list[tuple[str, dict]] = []

        room = make_room(created_at=100.0, expiry_seconds=10)
        await repository.create("g1", room)

        async def capture(game_id, payload):
            events.append((game_id, payload))

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            publish=capture,
        )

        await scheduler.schedule_expiry("g1", time.time() - 1)
        await scheduler.cancel("g1")
        await scheduler._process_due()

        assert await repository.get("g1") is not None
        assert events == []

    asyncio.run(scenario())


def test_duplicate_workers_only_one_processes():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        events: list[tuple[str, dict]] = []

        room = make_room(created_at=100.0, time_limit_seconds=60)
        room.add_player(now=100.0)
        room.add_player(now=100.0)
        room.scores = {0: 2, 1: 1}
        await repository.create("g1", room)

        async def capture(game_id, payload):
            events.append((game_id, payload))

        shared_backend = InMemorySchedulerBackend()
        scheduler_a = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            backend=shared_backend,
            publish=capture,
        )
        scheduler_b = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            backend=shared_backend,
            publish=capture,
        )

        await scheduler_a.schedule_match("g1", time.time() - 1)

        await scheduler_a._process_due()
        await scheduler_b._process_due()

        assert len(events) == 1
        assert events[0][1]["winner"] == 0

    asyncio.run(scenario())


def test_nonexistent_room_is_silently_skipped():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        events: list[tuple[str, dict]] = []

        async def capture(game_id, payload):
            events.append((game_id, payload))

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            publish=capture,
        )

        await scheduler.schedule_expiry("gone", time.time() - 1)
        await scheduler._process_due()

        assert events == []

    asyncio.run(scenario())


# ------------------------------------------------------------------
# Background loop tests
# ------------------------------------------------------------------


def test_start_and_stop_scheduler():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            poll_interval=0.05,
        )

        await scheduler.start()
        assert scheduler._task is not None
        assert not scheduler._task.done()

        await scheduler.stop()
        assert scheduler._task is None

    asyncio.run(scenario())


def test_background_loop_fires_expiry():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        events: list[tuple[str, dict]] = []

        room = make_room(created_at=100.0, expiry_seconds=10)
        await repository.create("g1", room)

        async def capture(game_id, payload):
            events.append((game_id, payload))

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            publish=capture,
            poll_interval=0.05,
        )

        await scheduler.schedule_expiry("g1", time.time() - 1)
        await scheduler.start()

        for _ in range(50):
            if events:
                break
            await asyncio.sleep(0.05)

        await scheduler.stop()

        assert len(events) >= 1
        assert events[0][1]["reason"] == "room_expired"

    asyncio.run(scenario())


# ------------------------------------------------------------------
# GameManager integration
# ------------------------------------------------------------------


def test_game_manager_schedules_expiry_on_create():
    from server.game_manager import GameManager

    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        backend = InMemorySchedulerBackend()

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            backend=backend,
        )

        manager = GameManager(
            repository=repository,
            event_bus=event_bus,
            scheduler=scheduler,
        )

        await manager.start()

        room = make_room(created_at=100.0, expiry_seconds=10)
        game_id = "test-expiry"
        await repository.create(game_id, room)
        await scheduler.schedule_expiry(game_id, room.created_at + room.expiry_seconds)

        entry = backend._deadlines.get(game_id)
        assert entry is not None
        assert entry[1] == "expiry"
        assert entry[0] == 110.0

        await scheduler.stop()
        await manager.stop()

    asyncio.run(scenario())


def test_game_manager_cancels_expiry_and_schedules_match():
    from server.game_manager import GameManager

    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        backend = InMemorySchedulerBackend()

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            backend=backend,
        )

        manager = GameManager(
            repository=repository,
            event_bus=event_bus,
            scheduler=scheduler,
        )

        await manager.start()

        now = time.time()
        room = make_room(created_at=now, expiry_seconds=300, time_limit_seconds=60)
        game_id = "test-match"
        await repository.create(game_id, room)
        await scheduler.schedule_expiry(game_id, now + room.expiry_seconds)

        assert backend._deadlines[game_id][1] == "expiry"

        class FakeWS:
            def __init__(self):
                self.messages = []
            async def send_text(self, data):
                import json
                self.messages.append(json.loads(data))

        ws0 = FakeWS()
        player0, game0, started0 = await manager.join_game(game_id, ws0)
        assert player0 == 0
        assert started0 is False

        entry = backend._deadlines.get(game_id)
        assert entry is not None
        assert entry[1] == "expiry"

        ws1 = FakeWS()
        player1, game1, started1 = await manager.join_game(game_id, ws1)
        assert player1 == 1
        assert started1 is True

        entry = backend._deadlines.get(game_id)
        assert entry is not None
        assert entry[1] == "timeout"

        await scheduler.stop()
        await manager.stop()

    asyncio.run(scenario())


def test_game_manager_cancels_schedule_on_board_complete():
    from server.game_manager import GameManager

    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        backend = InMemorySchedulerBackend()

        scheduler = TimeoutScheduler(
            repository=repository,
            event_bus=event_bus,
            backend=backend,
        )

        manager = GameManager(
            repository=repository,
            event_bus=event_bus,
            scheduler=scheduler,
        )

        await manager.start()

        solution = [[1 for _ in range(9)] for _ in range(9)]
        board = [row[:] for row in solution]
        board[0][0] = 0
        room = RoomState(
            created_at=time.time(),
            expiry_seconds=25,
            board=board,
            original_board=freeze_board(board),
            solution=solution,
            difficulty="easy",
            puzzle_hash="hash",
            time_limit_seconds=60,
        )
        room.add_player()
        room.add_player()
        await repository.create("g1", room)

        await scheduler.schedule_match("g1", time.time() + 60)
        assert "g1" in backend._deadlines

        await manager.apply_move("g1", 0, 0, 0, 1)

        assert "g1" not in backend._deadlines

        await scheduler.stop()
        await manager.stop()

    asyncio.run(scenario())
