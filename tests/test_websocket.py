import time

import pytest
from fastapi.testclient import TestClient

from server.main import app, manager


GAME_ID = "test-game"


def seed_game():
    """Create deterministic room state without calling external services."""
    solution = [[1 for _ in range(9)] for _ in range(9)]
    board = [row[:] for row in solution]
    board[0][0] = 0

    manager.games[GAME_ID] = {
        "created_at": time.time(),
        "expiry": 25,
        "players": [],
        "board": board,
        "original_board": [row[:] for row in board],
        "solution": solution,
        "difficulty": "easy",
        "hash": "test-hash",
        "scores": {0: 0, 1: 0},
        "start_time": None,
        "time_limit": 600,
        "started": False,
        "winner": None,
    }


@pytest.fixture(autouse=True)
def isolated_manager(monkeypatch):
    manager.games.clear()
    monkeypatch.setattr(manager, "verify_puzzle", lambda game_id: True)
    yield
    manager.games.clear()


def test_first_player_receives_init_and_waiting():
    seed_game()

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{GAME_ID}") as player:
            init = player.receive_json()
            waiting = player.receive_json()

            assert init["type"] == "init"
            assert init["player_id"] == 0
            assert init["started"] is False
            assert waiting == {
                "type": "waiting",
                "message": "Waiting for second player...",
            }


def test_move_is_rejected_before_second_player_joins(monkeypatch):
    seed_game()

    def verification_must_not_run(game_id):
        raise AssertionError("integrity check ran before start validation")

    monkeypatch.setattr(manager, "verify_puzzle", verification_must_not_run)

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{GAME_ID}") as player:
            player.receive_json()  # init
            player.receive_json()  # waiting

            player.send_json({
                "type": "move",
                "row": 0,
                "col": 0,
                "value": 1,
            })

            assert player.receive_json() == {
                "type": "error",
                "message": "Game has not started",
            }
            assert manager.games[GAME_ID]["board"][0][0] == 0


def test_started_room_handles_protocol_errors_and_broadcasts_moves():
    seed_game()

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{GAME_ID}") as player_0:
            player_0.receive_json()  # init
            player_0.receive_json()  # waiting

            with client.websocket_connect(f"/ws/{GAME_ID}") as player_1:
                second_init = player_1.receive_json()
                start_0 = player_0.receive_json()
                start_1 = player_1.receive_json()

                assert second_init["type"] == "init"
                assert second_init["player_id"] == 1
                assert second_init["started"] is True
                assert start_0["type"] == start_1["type"] == "start"
                assert len(start_0["board"]) == 9
                assert all(len(row) == 9 for row in start_0["board"])

                player_0.send_text("{not-json")
                assert player_0.receive_json() == {
                    "type": "error",
                    "message": "Invalid JSON",
                }

                player_0.send_json({"type": "ping"})
                assert player_0.receive_json() == {
                    "type": "error",
                    "message": "Unsupported message type",
                }

                player_0.send_json({
                    "type": "move",
                    "row": 9,
                    "col": 0,
                    "value": 1,
                })
                assert player_0.receive_json() == {
                    "type": "error",
                    "message": "row must be between 0 and 8",
                }
                assert manager.games[GAME_ID]["board"][0][0] == 0

                player_0.send_json({
                    "type": "move",
                    "row": 0,
                    "col": 0,
                    "value": 2,
                })
                incorrect_0 = player_0.receive_json()
                incorrect_1 = player_1.receive_json()
                assert incorrect_0 == incorrect_1
                assert incorrect_0["type"] == "update"
                assert incorrect_0["success"] is False
                assert incorrect_0["message"] == "Incorrect move"
                assert incorrect_0["board"][0][0] == 0

                player_0.send_json({
                    "type": "move",
                    "row": 0,
                    "col": 0,
                    "value": 1,
                })
                correct_0 = player_0.receive_json()
                correct_1 = player_1.receive_json()
                assert correct_0 == correct_1
                assert correct_0["type"] == "update"
                assert correct_0["success"] is True
                assert correct_0["scores"] == {"0": 1, "1": 0}
                assert correct_0["board"][0][0] == 1
                assert correct_0["game_over"] is True
                assert correct_0["winner"] == 0
