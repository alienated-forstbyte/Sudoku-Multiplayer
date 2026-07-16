"""Validation helpers for messages sent by WebSocket clients."""


def validate_move(
    message: object,
) -> tuple[tuple[int, int, int] | None, str | None]:
    """Validate a client move and return ``((row, col, value), None)``.

    Validation is intentionally independent of FastAPI so the protocol
    contract can be unit-tested without opening a WebSocket.
    """
    if not isinstance(message, dict):
        return None, "Message must be a JSON object"

    if message.get("type") != "move":
        return None, "Unsupported message type"

    ranges = {
        "row": (0, 8),
        "col": (0, 8),
        "value": (1, 9),
    }

    validated = {}
    for field, (minimum, maximum) in ranges.items():
        if field not in message:
            return None, f"Missing field: {field}"

        field_value = message[field]
        # bool is a subclass of int in Python, but true/false are not valid
        # Sudoku coordinates or values.
        if type(field_value) is not int:
            return None, f"{field} must be an integer"

        if not minimum <= field_value <= maximum:
            return None, f"{field} must be between {minimum} and {maximum}"

        validated[field] = field_value

    return (
        (validated["row"], validated["col"], validated["value"]),
        None,
    )
