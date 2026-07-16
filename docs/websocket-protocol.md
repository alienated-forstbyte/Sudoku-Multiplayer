# WebSocket Protocol

The multiplayer endpoint is:

```text
ws://<host>/ws/{game_id}
```

Messages are JSON objects. The server assigns a player ID from the player's
position in the room's connection list.

## Client message

### `move`

Attempts to place a value on the shared board.

```json
{
  "type": "move",
  "row": 0,
  "col": 1,
  "value": 7
}
```

Rows and columns are zero-based. Values are Sudoku digits from 1 through 9.
The server validates the message before reading or changing the board:

- the message must be a JSON object with `type: "move"`;
- `row`, `col`, and `value` are required;
- all three fields must be JSON integers (booleans, floats, and strings are
  rejected);
- `row` and `col` must be between 0 and 8;
- `value` must be between 1 and 9;
- a valid move is rejected until the second player has joined.

Extra object fields are currently ignored.

## Server messages

### `init`

Sent only to the connection that has just joined.

```json
{
  "type": "init",
  "player_id": 0,
  "started": false,
  "difficulty": "medium",
  "hash": "<puzzle hash>",
  "time_left": 600
}
```

### `waiting`

Sent to the first player while the room waits for player 2.

```json
{
  "type": "waiting",
  "message": "Waiting for second player..."
}
```

### `start`

Broadcast when the second player joins.

```json
{
  "type": "start",
  "board": [[0, 2, 3], ["..."]],
  "difficulty": "medium",
  "time_left": 600,
  "message": "Game started!"
}
```

The actual board is always a 9×9 integer matrix. Zero means an editable empty
cell; 1–9 means the server has accepted or supplied that value.

### `update`

Broadcast after a syntactically recognized move, whether correct or incorrect.

```json
{
  "type": "update",
  "success": true,
  "message": "Correct move",
  "board": [[0, 2, 3], ["..."]],
  "scores": {"0": 1, "1": 0},
  "time_left": 594,
  "game_over": false,
  "winner": null
}
```

JSON converts the integer score keys used by Python into string keys. A correct
move fills the one shared board and increments only its sender's score.

### `game_over`

Broadcast when a received message causes the server to notice that time has
elapsed.

```json
{
  "type": "game_over",
  "reason": "time_up",
  "winner": 0,
  "scores": {"0": 18, "1": 15}
}
```

`winner` is player ID `0`, player ID `1`, or the string `"draw"`.

The current browser checks a `game_over` boolean rather than explicitly
handling this event type, so timeout UI handling is incomplete.

### `error`

Sent for an invalid/full/expired room, malformed JSON, or a move received after
the game has a winner. It is also sent for unsupported message types, missing
move fields, invalid field types/ranges, moves before game start, and failed
puzzle-integrity checks.

```json
{
  "type": "error",
  "message": "Invalid JSON"
}
```

Some errors close the socket; others leave it connected.

## Current protocol constraints

- Only `move` is a defined client message type.
- The server does not yet return a structured error code.
- There is no protocol version or reconnect/resume token.
- Timeout detection depends on incoming messages.
- A disconnect removes the WebSocket from the list, so reconnecting can change
  the index-to-player relationship.
