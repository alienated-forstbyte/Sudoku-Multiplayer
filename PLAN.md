# Plan

This is the working roadmap for the Multiplayer Sudoku MLOps demo.
Architecture details live in [`docs/architecture.md`](docs/architecture.md).
Status and completed work live in [`PROGRESS.md`](PROGRESS.md).

Guiding rule for now: follow this plan in order. Usability feedback from solo
playtesting is recorded under **Deferred**, not inserted ahead of correctness
work unless something actually blocks development.

---

## Current focus

**Step 6 — Move room state to Redis and broadcasts to pub/sub**

### Why this is next

Typed rooms are still process-local, so restarts lose every game and multiple
workers cannot coordinate players or board updates. Redis can provide shared
state and a broadcast channel while WebSocket objects remain local to workers.

### Goals

1. Persist serializable room state outside the Python process.
2. Coordinate updates across multiple game-server workers through pub/sub.
3. Keep live WebSocket connections local and map them to room subscriptions.
4. Define expiry/cleanup behavior using Redis TTLs.

### Approach

1. Separate serializable game data from process-local player connections.
2. Add an async Redis repository interface and an in-memory test implementation.
3. Store room snapshots with TTL and use optimistic/atomic move updates.
4. Publish protocol events per room; each worker forwards them to local sockets.
5. Add Redis to Compose and test restart/multi-worker behavior.

### Out of scope for Step 6

- Stopping the client timer / lobby rematch (Deferred)
- Scheduled timeout tasks (Step 7)
- Long-term match history storage

### Success criteria

- A room survives a game-server restart while Redis remains available.
- Two workers can serve different players in the same room.
- Concurrent moves do not overwrite each other.
- Existing protocol response shapes remain unchanged.

---

## Full roadmap (ordered)

| Step | Item | Status |
| --- | --- | --- |
| 0 | Fix hash-chain add/verify and keep `original_board` | Done |
| 1 | Request validation + WebSocket integration tests | Done |
| 2 | Unify ML training/serving feature pipeline | Done |
| 3 | Move service URLs, timeouts, credentials to env vars | Done |
| 4 | Async HTTP client with connect/read timeouts | Done |
| 5 | Typed room state models instead of nested dicts | Done |
| 6 | Redis-backed rooms + pub/sub for multi-worker | **Next** |
| 7 | Background timeout tasks (not message-driven only) | Planned |
| 8 | Health checks, structured logs, metrics, degradation | Planned |
| 9 | Puzzle uniqueness check in the generator | Planned |
| 10 | Persist the hash chain beyond process memory | Planned |


---

## Deferred gameplay feedback

Recorded after a successful local match. Revisit **after Steps 1 and 2**.

1. Stop the browser countdown when the match ends (`update` with
   `game_over` or `game_over` event).
2. Show a completed-match UI (winner/draw, board locked).
3. “Play again” → return to lobby → create or join a new room.
4. Optional later: in-room rematch request/accept between the same two
   players.

Details also live under **Deferred gameplay feedback** in
[`docs/architecture.md`](docs/architecture.md).

---

## Completed Step 1 summary

- Added pure validation in `server/protocol.py`.
- Rejects non-object payloads, unsupported message types, missing fields,
  booleans/non-integers, invalid ranges, and valid moves sent before start.
- Added unit tests and offline WebSocket lifecycle/move tests.
- Documented the enforced protocol in `docs/websocket-protocol.md`.

## Completed Step 2 summary

- Added the versioned shared contract in `ml/feature_contract.py`.
- Dataset generation, training, local prediction, and HTTP serving use the
  same named feature DataFrame.
- Model artifacts carry feature and library metadata and are checked at load.
- Removed the duplicated ML-service feature implementation.
- Added contract, bundle, and endpoint tests; retrained at 95% held-out
  accuracy and smoke-tested `/predict` without feature-name warnings.

## Completed Step 3 summary

- Added `server/config.py` with a frozen `Settings` object and env parsing.
- `GameManager` reads service URLs, HTTP timeout, room expiry, and time limit
  from settings, and accepts an injected `Settings` for tests.
- Parameterized Compose with `${VARIABLE:-default}` and added `.env.example`
  (kept out of ignore rules).
- Added default/override/validation/injection tests.

## Completed Step 4 summary

- Added one lifespan-managed, pooled `httpx.AsyncClient`.
- Converted room creation and puzzle verification to async service calls.
- Added configurable, explicit connect/read/write/pool timeout values.
- Added offline mock-transport tests, including proof that a slow service call
  yields to unrelated coroutine work.
- Preserved WebSocket error feedback for unavailable integrity service.

## Completed Step 5 summary

- Added `RoomState` with typed boards, players, scores, timers, and winner.
- Made the original puzzle an immutable tuple-of-tuples.
- Moved join/start, expiry, countdown, timeout winner, move scoring, and
  completion invariants onto the model.
- Replaced all server-side string-key room access with attributes.
- Removed the broken shared-board `boards` lookup and added focused model tests.
