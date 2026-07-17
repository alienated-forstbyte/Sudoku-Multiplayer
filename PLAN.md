# Plan

This is the working roadmap for the Multiplayer Sudoku MLOps demo.
Architecture details live in [`docs/architecture.md`](docs/architecture.md).
Status and completed work live in [`PROGRESS.md`](PROGRESS.md).

Guiding rule for now: follow this plan in order. Usability feedback from solo
playtesting is recorded under **Deferred**, not inserted ahead of correctness
work unless something actually blocks development.

---

## Current focus

**Step 5 — Replace nested room dictionaries with typed state models**

### Why this is next

Room state is currently a dictionary of loosely related keys. Typos such as the
old `boards`/`board` mismatch are discovered only at runtime, and refactoring
state across WebSocket and manager code is error-prone.

### Goals

1. Define typed room/player state with clear defaults and invariants.
2. Replace string-key indexing in `GameManager` and the WebSocket endpoint.
3. Preserve the existing protocol and gameplay behavior.
4. Keep serialization at the protocol boundary explicit.

### Approach

1. Add dataclasses for room state (and player connection if useful).
2. Type the `games` mapping and move timer/score operations onto the model.
3. Update manager and endpoint access incrementally.
4. Add invariant/unit tests, then rerun all WebSocket integration tests.

### Out of scope for Step 5

- Stopping the client timer / lobby rematch (Deferred)
- Redis and background timeouts
- Persistence or cross-worker serialization

### Success criteria

- Core room state no longer relies on untyped string-key dictionaries.
- Existing HTTP/WebSocket response shapes are unchanged.
- All protocol and gameplay tests pass.

---

## Full roadmap (ordered)

| Step | Item | Status |
| --- | --- | --- |
| 0 | Fix hash-chain add/verify and keep `original_board` | Done |
| 1 | Request validation + WebSocket integration tests | Done |
| 2 | Unify ML training/serving feature pipeline | Done |
| 3 | Move service URLs, timeouts, credentials to env vars | Done |
| 4 | Async HTTP client with connect/read timeouts | Done |
| 5 | Typed room state models instead of nested dicts | **Next** |
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

## Completed Step 4 summary

- Added one lifespan-managed, pooled `httpx.AsyncClient`.
- Converted room creation and puzzle verification to async service calls.
- Added configurable, explicit connect/read/write/pool timeout values.
- Added offline mock-transport tests, including proof that a slow service call
  yields to unrelated coroutine work.
- Preserved WebSocket error feedback for unavailable integrity service.
