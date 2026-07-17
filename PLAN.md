# Plan

This is the working roadmap for the Multiplayer Sudoku MLOps demo.
Architecture details live in [`docs/architecture.md`](docs/architecture.md).
Status and completed work live in [`PROGRESS.md`](PROGRESS.md).

Guiding rule for now: follow this plan in order. Usability feedback from solo
playtesting is recorded under **Deferred**, not inserted ahead of correctness
work unless something actually blocks development.

---

## Current focus

**Step 7 — Run room expiry and match timeouts independently of messages**

### Why this is next

Timers are still checked only when a player sends a message. An idle expired
room remains stored, and a finished match does not emit `game_over` until
someone interacts. Redis now provides the shared coordination needed for an
independent scheduler.

### Goals

1. Expire waiting rooms at their deadline without client activity.
2. Finish matches and publish `game_over` exactly once at the time limit.
3. Coordinate multiple workers so only one processes each deadline.
4. Recover pending deadlines after a worker restart.

### Approach

1. Store room deadlines in a Redis sorted set (with an in-memory test queue).
2. Run a lifespan-managed scheduler that claims due items atomically.
3. Re-check room state under the repository mutation lock before expiring or
   finishing it.
4. Publish one timeout event through the existing room event bus.
5. Test idle timeout, cancellation/state changes, duplicate workers, and
   restart recovery.

### Out of scope for Step 7

- Stopping the client timer / lobby rematch (Deferred)
- Durable match history after cleanup
- General-purpose background job infrastructure

### Success criteria

- Waiting rooms disappear at their configured expiry without messages.
- Started games broadcast `game_over` at their deadline while idle.
- Multiple workers cannot publish duplicate terminal events.

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
| 6 | Redis-backed rooms + pub/sub for multi-worker | Done |
| 7 | Background timeout tasks (not message-driven only) | **Next** |
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

## Completed Step 6 summary

- Split serializable `RoomState` snapshots from worker-local WebSocket objects.
- Added in-memory and Redis repositories with atomic mutation boundaries.
- Added in-memory and Redis event buses for worker-local socket delivery.
- Added Redis AOF, room TTL configuration, and graceful slot release.
- Verified atomic concurrent mutations, two Redis subscribers, restart
  persistence, and two players connected through separate server workers.
