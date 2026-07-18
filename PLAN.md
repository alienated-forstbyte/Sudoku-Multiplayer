# Plan

This is the working roadmap for the Multiplayer Sudoku MLOps demo.
Architecture details live in `docs/architecture.md`.
Status and completed work live in `PROGRESS.md`.

Guiding rule for now: follow this plan in order. Usability feedback from solo
playtesting is recorded under **Deferred**, not inserted ahead of correctness
work unless something actually blocks development.

---

## Current focus

**Step 8 — Health checks, structured logs, metrics, degradation**

### Why this is next

The core correctness pipeline (validation, ML parity, config, async HTTP,
typed state, Redis, scheduler) is complete. The next layer adds operational
visibility and resilience for production-like deployments.

### Goals

1. Add health-check endpoints for each service.
2. Introduce structured logging with correlation IDs.
3. Expose basic metrics (move counts, latency, error rates).
4. Degrade gracefully when optional services (ML, blockchain) are unavailable.

### Approach

TBD — to be detailed when Step 8 begins.

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
| 7 | Background timeout tasks (not message-driven only) | Done |
| 8 | Health checks, structured logs, metrics, degradation | **Next** |
| 9 | Puzzle uniqueness check in the generator | Planned |
| 10 | Persist the hash chain beyond process memory | Planned |

---

## Deferred gameplay feedback

Recorded after a successful local match. Revisit **after Steps 1 and 2**.

1. Stop the browser countdown when the match ends (`update` with
   `game_over` or `game_over` event).
2. Show a completed-match UI (winner/draw, board locked).
3. "Play again" → return to lobby → create or join a new room.
4. Optional later: in-room rematch request/accept between the same two
   players.

Details also live under **Deferred gameplay feedback** in
`docs/architecture.md`.

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

## Completed Step 7 summary

- Added `server/scheduler.py` with `TimeoutScheduler` and pluggable
  `SchedulerBackend` protocol.
- `InMemorySchedulerBackend` for tests; `RedisSchedulerBackend` (sorted set
  with atomic claim) for multi-worker production.
- Background polling at configurable `SCHEDULER_POLL_INTERVAL` with
  repository-lock re-check before every action.
- Waiting rooms expire and are deleted without client interaction.
- Started matches broadcast exactly one `game_over` at the time limit.
- `GameManager` schedules expiry on creation, switches to match timeout on
  start, and cancels on board completion.
- Message-driven checks retained as defense-in-depth.
- 15 scheduler tests (backend, handlers, cancellation, duplicate workers,
  background loop, GameManager integration). Full suite: 60/60 pass.
