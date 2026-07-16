# Architecture and Runtime Flow

This document explains the current implementation. It deliberately separates
what the prototype does today from improvements that would be needed for a
production deployment.

**Project tracking**

- Roadmap and next-step plan: [`../PLAN.md`](../PLAN.md)
- Status and completed work: [`../PROGRESS.md`](../PROGRESS.md)
- WebSocket message contract: [`websocket-protocol.md`](websocket-protocol.md)

## Components

### Browser client

`client/index.html` and `client/app.js` provide the user interface. The browser
uses HTTP only to create a room; joining, moves, board updates, scores, and game
completion use one WebSocket connection per player.

The client keeps a local countdown for display, but the server's timestamps are
authoritative. Each server update can reduce the displayed time.

### Game server

`server/main.py` owns the HTTP and WebSocket endpoints.
`server/game_manager.py` owns the in-memory room dictionary and talks to the ML
and hash-chain services.

A room contains:

- creation and expiration timestamps;
- up to two WebSocket connections;
- one shared live puzzle board, an immutable `original_board`, and its solution;
- the predicted difficulty and puzzle hash (of `original_board`);
- scores for player IDs `0` and `1`;
- game start time, time limit, and winner.

There is no database or message broker for game state. This makes the code easy
to study, but all connections for a room must reach the same Python process.

Move payloads are not yet validated on the server beyond JSON parsing. Step 1
in [`PLAN.md`](../PLAN.md) adds bounds/type checks and protocol integration
tests.

### Sudoku engine

`engine/generator.py` creates a complete valid grid with randomized recursive
backtracking. It then copies that grid and removes a random number of clues:

- easy: 25–35 removed cells;
- medium: 35–45 removed cells;
- hard: 45–60 removed cells.

The completed grid is retained as the server's answer key. Removing clues from
a valid solution guarantees at least one solution, but the current algorithm
does not check whether that solution is unique.

`engine/solver.py` provides the same backtracking idea in a reusable solver. It
mutates the board passed to it.

### ML service

The training pipeline is split across:

1. `ml/dataset.py`, which generates labeled synthetic puzzles and features;
2. `ml/train.py`, which trains and evaluates a Random Forest;
3. `ml_service/app.py`, which loads a serialized model and serves `POST
   /predict`.

Feature order is part of a model's API, even though it is not represented by an
HTTP route. The current serving order differs from training, so unifying the
feature extractor is a prerequisite for trustworthy predictions (Step 2).

### Hash-chain service

`blockchain/app.py` appends puzzle data to an in-memory sequence. `/add` and
`/verify` both use the same `hash_data` helper over the puzzle payload, so
integrity checks round-trip. Each block also stores a chain link hash that
folds in `previous_hash`, which illustrates tamper-evident chaining for
learning. It is not a decentralized blockchain: there is no peer network,
consensus, persistence, or public-key signing.

Rooms keep an immutable `original_board` for verification and a separate live
`board` for gameplay progress.

### Analytics

Compose starts Matomo and MariaDB. The browser also includes Microsoft Clarity.
These systems are independent from gameplay and should not be required for
core game correctness. Production use would require privacy disclosures,
consent handling where applicable, and non-default credentials.

## Room lifecycle

1. The browser sends `POST /create`.
2. The game manager generates a complete board and removes clues.
3. It sends the puzzle to the ML service for a difficulty label.
4. It sends serialized puzzle data to the hash-chain service.
5. It stores the room in memory and returns its UUID.
6. Player 0 connects and receives `init` followed by `waiting`.
7. Player 1 connects; the server records the start time and broadcasts `start`.
8. A player sends a move. The server checks puzzle integrity, compares the move
   with the answer key, updates the shared board and score, then broadcasts an
   `update`.
9. Filling the final empty cell makes that submitting player the winner.
10. If a received message observes an elapsed timer, the server chooses the
    higher score or a draw and broadcasts `game_over`.

Room expiration and game timeout differ:

- An unstarted room expires 25 seconds after creation.
- A started room has a 600-second game limit.
- Neither rule currently has a background scheduler; checks happen while
  handling connections/messages.

## State and concurrency

FastAPI endpoints are asynchronous, but `requests.post` is synchronous. Calls
to the ML and hash-chain services therefore block the event-loop thread during
room creation and move verification.

The mutable room dictionary also has no locking or transactional boundary.
This is acceptable for understanding the prototype, but concurrent moves to
the same cell can race as the architecture evolves.

## Roadmap pointer

The ordered improvement list, current-step plan, and deferred gameplay items
are maintained in [`PLAN.md`](../PLAN.md). Do not fork a second prioritization
here; keep this file focused on how the system works today.

Summary of the active order:

1. Request validation + WebSocket integration tests (**next**)
2. Unify ML training/serving feature pipeline
3. Env-based service URLs / credentials
4. Async HTTP client with timeouts
5. Typed room state models
6. Redis rooms + pub/sub
7. Background timeout tasks
8. Health checks, logs, metrics, degradation
9. Puzzle uniqueness in generation
10. Persist the hash chain

## Deferred gameplay feedback

The following issues were observed during a successful two-player test but are
deliberately deferred while the correctness roadmap in [`PLAN.md`](../PLAN.md)
is in progress:

- Stop the browser countdown immediately when either an `update` or
  `game_over` event ends the match.
- Show a completed-match state that disables the board and clearly identifies
  the winner or draw.
- Add a “Play again” action that returns each user to the lobby, where they can
  create or join another room.
- Consider an in-room rematch request/accept flow only after the simpler lobby
  return works reliably.

Revisit after Steps 1 and 2 (validation/tests and ML feature parity). These are
usability issues rather than blockers for the sole-user development
environment.
