import json

from fastapi.testclient import TestClient

from blockchain.app import app, chain, hash_data


def setup_function():
    chain.clear()


def test_hash_data_is_stable():
    assert hash_data('[[0,1],[2,3]]') == hash_data('[[0,1],[2,3]]')
    assert hash_data('[[0,1],[2,3]]') != hash_data('[[9,1],[2,3]]')


def test_add_verify_round_trip():
    client = TestClient(app)
    puzzle = [[0] * 9 for _ in range(9)]
    payload = json.dumps(puzzle)

    add_response = client.post("/add", json={"data": payload})
    assert add_response.status_code == 200
    puzzle_hash = add_response.json()["hash"]
    assert puzzle_hash == hash_data(payload)

    verify_response = client.post(
        "/verify",
        json={"data": payload, "hash": puzzle_hash},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["valid"] is True


def test_verify_rejects_tampered_data():
    client = TestClient(app)
    original = json.dumps([[1] * 9 for _ in range(9)])
    tampered = json.dumps([[2] * 9 for _ in range(9)])

    puzzle_hash = client.post("/add", json={"data": original}).json()["hash"]

    verify_response = client.post(
        "/verify",
        json={"data": tampered, "hash": puzzle_hash},
    )
    assert verify_response.json()["valid"] is False


def test_original_board_survives_live_board_mutation():
    """Mirrors the game-server contract: hash original, mutate live board."""
    client = TestClient(app)
    original_board = [[0] * 9 for _ in range(9)]
    live_board = [row[:] for row in original_board]
    payload = json.dumps(original_board)

    puzzle_hash = client.post("/add", json={"data": payload}).json()["hash"]

    live_board[0][0] = 5

    still_valid = client.post(
        "/verify",
        json={"data": json.dumps(original_board), "hash": puzzle_hash},
    ).json()["valid"]
    assert still_valid is True

    live_as_original = client.post(
        "/verify",
        json={"data": json.dumps(live_board), "hash": puzzle_hash},
    ).json()["valid"]
    assert live_as_original is False
