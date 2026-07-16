# Plan

This is the working roadmap for the Multiplayer Sudoku MLOps demo.
Architecture details live in [`docs/architecture.md`](docs/architecture.md).
Status and completed work live in [`PROGRESS.md`](PROGRESS.md).

Guiding rule for now: follow this plan in order. Usability feedback from solo
playtesting is recorded under **Deferred**, not inserted ahead of correctness
work unless something actually blocks development.

---

## Current focus

**Step 1 — Request validation and integration tests for WebSocket messages**

### Why this is next

The move path currently indexes the board with untrusted `row` / `col` /
`value` fields. Malformed JSON is handled, but missing fields, wrong types,
out-of-range indexes, unknown message types, and pre-start moves are not.
Without tests around the protocol, later refactors (ML parity, env config,
Redis) are harder to trust.

### Goals

1. Reject invalid client messages with a clear `error` response instead of
   crashing or silently ignoring them.
2. Document the validation rules in `docs/websocket-protocol.md`.
3. Cover the room lifecycle with automated tests so `init`, `waiting`,
   `start`, `update`, and `error` stay stable.

### Approach

#### A. Extract a small validator

Add a pure helper (for example `server/protocol.py` or
`server/validation.py`) that:

- accepts a parsed JSON object;
- returns either a validated move `(row, col, value)` or an error string;
- enforces:
  - `type` must be `"move"` (unknown types → error);
  - `row`, `col`, `value` must be integers (reject bools/floats/strings);
  - `row` and `col` in `0..8`;
  - `value` in `1..9`.

Keep validation free of FastAPI / WebSocket dependencies so unit tests can
call it directly.

#### B. Wire validation into `server/main.py`

Before board indexing:

1. If the game has not started, reject moves with an `error`
   (`"Game has not started"`).
2. Run the validator; on failure send `{"type":"error","message":...}` and
   `continue`.
3. Only then run integrity check, apply move logic, and broadcast `update`.

Do not change scoring or win rules in this step.

#### C. Make GameManager easier to test

Integration tests should not require live Docker DNS (`ml_service`,
`blockchain`) for every case. Prefer one of:

- inject optional URLs / callables for predict and hash services; or
- add a test-only path that stubs those HTTP calls.

Keep production Docker behavior unchanged.

#### D. Tests to add

| Test | What it proves |
| --- | --- |
| Unit: valid move | Accepted shape returns `(row, col, value)` |
| Unit: bad type / bounds / missing fields | Clear error strings |
| Integration: create + first join | `init` then `waiting` |
| Integration: second join | both receive `start` with a 9×9 board |
| Integration: correct move | both receive `update`, scores change |
| Integration: incorrect move | `update` with `success: false`, board unchanged |
| Integration: out-of-range move | `error`, no board mutation |
| Integration: move before start | `error` |
| Integration: unknown message type | `error` |
| Integration: invalid JSON | `error` |

Use FastAPI / Starlette WebSocket test clients where possible. Mock or stub
ML and hash-chain HTTP so tests run offline with `make test`.

#### E. Docs to update when Step 1 lands

- `docs/websocket-protocol.md` — server-side validation rules
- `PROGRESS.md` — mark Step 1 done
- This file — set Current focus to Step 2

### Out of scope for Step 1

- Stopping the client timer / lobby rematch (Deferred)
- ML feature-order unification (Step 2)
- Environment variables, Redis, background timeouts
- Changing Matomo / Clarity

### Success criteria

- Malformed moves never raise uncaught exceptions in the WebSocket loop.
- `make test` covers validator unit tests and at least the join/start/move
  happy path plus one invalid-move case.
- Protocol docs match the implemented rules.

---

## Full roadmap (ordered)

| Step | Item | Status |
| --- | --- | --- |
| 0 | Fix hash-chain add/verify and keep `original_board` | Done |
| 1 | Request validation + WebSocket integration tests | **Next** |
| 2 | Unify ML training/serving feature pipeline | Planned |
| 3 | Move service URLs, timeouts, credentials to env vars | Planned |
| 4 | Async HTTP client with connect/read timeouts | Planned |
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

## Step 2 preview (after Step 1)

Unify feature extraction so training (`ml/dataset.py` / `ml/train.py`) and
serving (`ml_service/app.py`) use one ordered feature vector. Retrain, copy
the model into both expected paths, and add a contract test that fails if
column order drifts.
