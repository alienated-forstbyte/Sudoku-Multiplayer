# Progress

Living status log for the Multiplayer Sudoku MLOps demo.
Roadmap and next-step detail: [`PLAN.md`](PLAN.md).
System design: [`docs/architecture.md`](docs/architecture.md).

## Snapshot

| Area | State |
| --- | --- |
| Core 2-player shared-board loop | Working (manual playtest) |
| Hash-chain integrity on moves | Fixed |
| Docs / Makefile / run script | In place |
| WebSocket input validation | Complete (Step 1) |
| ML train/serve feature parity | Next (Step 2) |
| Post-match timer + rematch UX | Deferred |

## Completed

### Documentation and tooling

- Rewrote [`Readme.md`](Readme.md) to match the real shared-board design,
  services, ports, and known limitations.
- Added [`docs/architecture.md`](docs/architecture.md) and
  [`docs/websocket-protocol.md`](docs/websocket-protocol.md).
- Added educational comments/docstrings on engine, server, ML service, and
  hash-chain code.
- Added [`Makefile`](Makefile), [`run.sh`](run.sh), and root
  [`requirements.txt`](requirements.txt) for install → train → compose → test.

### Step 0 — Hash-chain verification

- Canonical `hash_data()` shared by `/add` and `/verify` in
  `blockchain/app.py`.
- Rooms store immutable `original_board`; verification no longer uses the
  mutating live board.
- Failed integrity checks send a WebSocket `error` instead of silently
  skipping the move.
- Added [`tests/test_blockchain.py`](tests/test_blockchain.py) (round-trip,
  tamper, original-vs-live board).

### Step 1 — Validation and WebSocket integration tests

- Added the framework-independent move validator in `server/protocol.py`.
- Rejects non-object messages, unsupported types, missing fields, non-integer
  values (including booleans), and out-of-range coordinates/values.
- Rejects moves until the second player joins.
- Added validator unit tests and offline WebSocket tests for `init`, `waiting`,
  `start`, malformed JSON, unsupported messages, invalid and incorrect moves,
  successful broadcasts, scoring, and completion.
- Removed the unused import that loaded a model while importing the game
  server, allowing protocol tests to run without an ML artifact.
- Updated `docs/websocket-protocol.md`.
- Follow-up after playtest: resilient `broadcast()` so a dead peer cannot abort
  move delivery; integrity-service failures return an `error` instead of
  killing the WebSocket handler; client shows move feedback text for correct /
  incorrect / error results.

### Playtest notes (not fixed yet)

- Moves and board sync worked well in a real two-player session.
- After the match ended, the client timer kept counting.
- There is no lobby return / “play again” path yet.

These are tracked under **Deferred** in [`PLAN.md`](PLAN.md) and
[`docs/architecture.md`](docs/architecture.md).

## In progress

_Nothing actively in progress. Next work is Step 2._

## Next

**Step 2 — Unify the ML training and serving feature pipeline**

See the detailed approach in [`PLAN.md`](PLAN.md#current-focus).

Short checklist:

- [ ] Inventory training, local inference, and service features
- [ ] Create one named, ordered feature contract
- [ ] Reuse it in dataset generation, training, and serving
- [ ] Add parity and prediction tests
- [ ] Retrain and place the model artifact
- [ ] Verify `make train`, `make test`, and `/predict`

## Deferred

After Steps 1–2:

- Stop browser timer on match end
- Completed-match UI (winner/draw, locked board)
- “Play again” → lobby → new room
- Optional later: in-room rematch handshake

## How to update this file

When finishing a step:

1. Move the step into **Completed** with a short bullet list.
2. Clear **In progress** or set the next step.
3. Check off the Step checklist and refresh the Snapshot table.
4. Update the status column in [`PLAN.md`](PLAN.md).
