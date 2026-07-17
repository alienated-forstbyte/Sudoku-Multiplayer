import pytest

from server.models import RoomState, freeze_board


class DummyConnection:
    async def send_text(self, _data):
        pass


def make_room(**overrides):
    solution = [[1 for _ in range(9)] for _ in range(9)]
    board = [row[:] for row in solution]
    board[0][0] = 0
    values = {
        "created_at": 100.0,
        "expiry_seconds": 25,
        "board": board,
        "original_board": freeze_board(board),
        "solution": solution,
        "difficulty": "easy",
        "puzzle_hash": "hash",
        "time_limit_seconds": 60,
    }
    values.update(overrides)
    return RoomState(**values)


def test_room_rejects_invalid_board_shape():
    with pytest.raises(ValueError, match="board must be a 9x9 board"):
        make_room(board=[[0]])


def test_original_board_is_an_immutable_copy():
    room = make_room()

    room.board[0][0] = 1

    assert room.original_board[0][0] == 0
    with pytest.raises(TypeError):
        room.original_board[0][0] = 1


def test_second_player_starts_room_and_timer():
    room = make_room()
    player_0 = DummyConnection()
    player_1 = DummyConnection()

    assert room.add_player(player_0, now=150.0) == 0
    assert room.started is False
    assert room.add_player(player_1, now=155.0) == 1

    assert room.started is True
    assert room.start_time == 155.0
    assert room.add_player(DummyConnection()) is None
    assert room.time_left(now=165.0) == 50
    assert room.is_timed_out(now=215.0) is True


def test_unstarted_room_expiry_stops_after_start():
    room = make_room()

    assert room.is_expired(now=125.0) is False
    assert room.is_expired(now=126.0) is True

    room.add_player(DummyConnection())
    room.add_player(DummyConnection(), now=130.0)
    assert room.is_expired(now=1_000.0) is False


def test_apply_move_updates_score_and_winner_only_when_correct():
    room = make_room()

    assert room.apply_move(0, 0, 0, 2) == (False, "Incorrect move")
    assert room.scores == {0: 0, 1: 0}
    assert room.winner is None

    assert room.apply_move(0, 0, 0, 1) == (True, "Correct move")
    assert room.scores == {0: 1, 1: 0}
    assert room.winner == 0
    assert room.is_complete() is True


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ({0: 2, 1: 1}, 0),
        ({0: 1, 1: 2}, 1),
        ({0: 2, 1: 2}, "draw"),
    ],
)
def test_timeout_winner_is_score_based(scores, expected):
    room = make_room(scores=scores)

    assert room.finish_on_timeout() == expected
    assert room.winner == expected
