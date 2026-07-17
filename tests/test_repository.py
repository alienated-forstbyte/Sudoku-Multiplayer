import asyncio
import json
import time

from server.events import InMemoryEventBus
from server.game_manager import GameManager
from server.models import RoomState, freeze_board
from server.repository import InMemoryRoomRepository


class RecordingConnection:
    def __init__(self):
        self.messages = []

    async def send_text(self, data):
        self.messages.append(json.loads(data))


def make_room():
    solution = [[1 for _ in range(9)] for _ in range(9)]
    board = [row[:] for row in solution]
    board[0][0] = 0
    return RoomState(
        created_at=time.time(),
        expiry_seconds=25,
        board=board,
        original_board=freeze_board(board),
        solution=solution,
        difficulty="easy",
        puzzle_hash="hash",
        time_limit_seconds=600,
    )


def test_room_snapshot_round_trip_preserves_types():
    room = make_room()
    room.add_player(now=101)
    snapshot = json.loads(json.dumps(room.to_dict()))

    restored = RoomState.from_dict(snapshot)

    assert restored == room
    assert restored.original_board == room.original_board
    assert restored.scores == {0: 0, 1: 0}


def test_in_memory_repository_serializes_concurrent_mutations():
    async def scenario():
        repository = InMemoryRoomRepository()
        await repository.create("game", make_room())

        def increment(room):
            room.scores[0] += 1

        await asyncio.gather(
            *(repository.mutate("game", increment) for _ in range(50))
        )
        return await repository.get("game")

    room = asyncio.run(scenario())

    assert room.scores[0] == 50


def test_two_managers_share_state_and_broadcast_events():
    async def scenario():
        repository = InMemoryRoomRepository()
        event_bus = InMemoryEventBus()
        manager_0 = GameManager(repository=repository, event_bus=event_bus)
        manager_1 = GameManager(repository=repository, event_bus=event_bus)
        connection_0 = RecordingConnection()
        connection_1 = RecordingConnection()

        await repository.create("game", make_room())
        await manager_0.start()
        await manager_1.start()

        player_0, room_0, started_0 = await manager_0.join_game(
            "game", connection_0
        )
        player_1, room_1, started_1 = await manager_1.join_game(
            "game", connection_1
        )

        await manager_1.broadcast("game", {"type": "start"})
        room, success, message = await manager_0.apply_move(
            "game", player_0, 0, 0, 1
        )
        await manager_0.broadcast("game", {
            "type": "update",
            "success": success,
            "message": message,
            "scores": room.scores,
        })
        persisted = await manager_1.get_game("game")

        return (
            player_0,
            player_1,
            started_0,
            started_1,
            connection_0.messages,
            connection_1.messages,
            persisted,
        )

    result = asyncio.run(scenario())
    (
        player_0,
        player_1,
        started_0,
        started_1,
        messages_0,
        messages_1,
        persisted,
    ) = result

    assert (player_0, player_1) == (0, 1)
    assert started_0 is False
    assert started_1 is True
    assert messages_0 == messages_1
    assert [message["type"] for message in messages_0] == ["start", "update"]
    assert persisted.board[0][0] == 1
    assert persisted.scores == {0: 1, 1: 0}


def test_new_manager_reads_existing_room_from_repository():
    async def scenario():
        repository = InMemoryRoomRepository()
        await repository.create("game", make_room())

        restarted_manager = GameManager(repository=repository)
        return await restarted_manager.get_game("game")

    room = asyncio.run(scenario())

    assert room is not None
    assert room.puzzle_hash == "hash"
