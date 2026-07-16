import pytest

from server.protocol import validate_move


def test_validate_move_accepts_valid_payload():
    move, error = validate_move({
        "type": "move",
        "row": 0,
        "col": 8,
        "value": 9,
    })

    assert move == (0, 8, 9)
    assert error is None


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ([], "Message must be a JSON object"),
        ({"type": "ping"}, "Unsupported message type"),
        ({"type": "move", "col": 0, "value": 1}, "Missing field: row"),
        (
            {"type": "move", "row": "0", "col": 0, "value": 1},
            "row must be an integer",
        ),
        (
            {"type": "move", "row": True, "col": 0, "value": 1},
            "row must be an integer",
        ),
        (
            {"type": "move", "row": -1, "col": 0, "value": 1},
            "row must be between 0 and 8",
        ),
        (
            {"type": "move", "row": 0, "col": 9, "value": 1},
            "col must be between 0 and 8",
        ),
        (
            {"type": "move", "row": 0, "col": 0, "value": 0},
            "value must be between 1 and 9",
        ),
    ],
)
def test_validate_move_rejects_invalid_payload(payload, expected_error):
    move, error = validate_move(payload)

    assert move is None
    assert error == expected_error
