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
`server/game_manager.py` coordinates a room repository, an event bus, local
WebSocket connections, and the ML/hash-chain services. `server/models.py`
defines serializable room fields and owns joining, expiry/timer calculations,
scoring, completion, and timeout-winner invariants.

A room contains:

- creation and expiration timestamps;
- up to two connected player IDs (WebSocket objects stay worker-local);
- one shared live puzzle board, an immutable `original_board`, and its solution;
- the predicted difficulty and puzzle hash (of `original_board`);
- scores for player IDs `0` and `1`;
- game start time, time limit, and winner.

`server/repository.py` stores room snapshots in Redis with a TTL and uses a
per-room distributed lock for atomic read-modify-write operations.
`server/events.py` publishes room events through Redis pub/sub; every worker
subscribes and forwards those events only to its own local WebSockets. Tests use
equivalent in-memory repository/event-bus implementations.

Move payloads are validated by the pure helper in `server/protocol.py` before
the server indexes the board. The WebSocket integration tests seed room state
directly and stub puzzle verification, so they run without Docker services.

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

Feature order is part of the model API. `ml/feature_contract.py` defines one
versioned tuple of names and one extractor shared by dataset generation, local
prediction, and the HTTP service. Training saves that metadata beside the
estimator in a model bundle; serving validates it at startup and uses a named
DataFrame, preventing silent column-order drift.

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

- An unstarted room expires after `ROOM_EXPIRY_SECONDS` (default 25).
- A started room has a `GAME_TIME_LIMIT_SECONDS` limit (default 600).
- Neither rule currently has a background scheduler; checks happen while
  handling connections/messages.

## Configuration

`server/config.py` resolves a frozen `Settings` object from environment
variables with development defaults. `GameManager` accepts an optional
`Settings` for tests and otherwise loads from the environment. Service URLs,
connect/read timeouts, room expiry, and the game time limit are configurable,
and Compose supplies them through `${VARIABLE:-default}` expressions and an
optional `.env`.

## State and concurrency

FastAPI owns one pooled `httpx.AsyncClient` through its application lifespan.
Room creation and move verification await that client, so slow dependencies do
not block unrelated WebSocket work. `SERVICE_CONNECT_TIMEOUT` and
`SERVICE_READ_TIMEOUT` bound connection establishment and response waiting.

`RoomState` removes string-key ambiguity. Repository mutations provide the
transaction boundary: the in-memory backend uses an async lock and Redis uses
a distributed per-room lock. This prevents concurrent workers from overwriting
each other's moves. Redis AOF persists snapshots across game-server restarts;
live sockets reconnect separately because they cannot be serialized.

## Roadmap pointer

The ordered improvement list, current-step plan, and deferred gameplay items
are maintained in [`PLAN.md`](../PLAN.md). Do not fork a second prioritization
here; keep this file focused on how the system works today.

Summary of the active order:

1. Request validation + WebSocket integration tests (**done**)
2. Unify ML training/serving feature pipeline (**done**)
3. Env-based service URLs / credentials (**done**)
4. Async HTTP client with timeouts (**done**)
5. Typed room state models (**done**)
6. Redis rooms + pub/sub (**done**)
7. Background timeout tasks (**next**)
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
