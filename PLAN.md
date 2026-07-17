# Plan

This is the working roadmap for the Multiplayer Sudoku MLOps demo.
Architecture details live in [`docs/architecture.md`](docs/architecture.md).
Status and completed work live in [`PROGRESS.md`](PROGRESS.md).

Guiding rule for now: follow this plan in order. Usability feedback from solo
playtesting is recorded under **Deferred**, not inserted ahead of correctness
work unless something actually blocks development.

---

## Current focus

**Step 4 — Use an async HTTP client with explicit connect/read timeouts**

### Why this is next

Room creation and move verification call the ML and hash-chain services with
synchronous `requests.post`, which blocks the event loop under load. An async
client keeps the WebSocket server responsive and makes timeouts explicit.

### Goals

1. Replace synchronous calls with an async client (e.g. `httpx.AsyncClient`).
2. Set explicit connect and read timeouts sourced from settings.
3. Keep failures mapped to the existing WebSocket `error` behavior.
4. Preserve offline testability (no real network in unit tests).

### Approach

1. Add an async HTTP dependency and a shared client lifecycle.
2. Make `create_game`/`verify_puzzle` awaitable or call them off the loop.
3. Thread settings-based connect/read timeouts through each request.
4. Update tests to stub the async client; keep integration tests offline.
5. Confirm a slow dependency no longer blocks other rooms.

### Out of scope for Step 4

- Stopping the client timer / lobby rematch (Deferred)
- Redis and background timeouts
- Retry/circuit-breaker policies beyond simple timeouts

### Success criteria

- No synchronous service HTTP call remains on the event-loop path.
- Connect/read timeouts are explicit and configurable.
- Tests run offline and a stalled dependency does not block other players.

---

## Full roadmap (ordered)

| Step | Item | Status |
| --- | --- | --- |
| 0 | Fix hash-chain add/verify and keep `original_board` | Done |
| 1 | Request validation + WebSocket integration tests | Done |
| 2 | Unify ML training/serving feature pipeline | Done |
| 3 | Move service URLs, timeouts, credentials to env vars | Done |
| 4 | Async HTTP client with connect/read timeouts | **Next** |
| 5 | Typed room state models instead of nested dicts | Planned |
| 6 | Redis-backed rooms + pub/sub for multi-worker | Planned |
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
