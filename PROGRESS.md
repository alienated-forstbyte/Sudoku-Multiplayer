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
| WebSocket input validation | Not started (Step 1) |
| ML train/serve feature parity | Broken / planned (Step 2) |
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

### Playtest notes (not fixed yet)

- Moves and board sync worked well in a real two-player session.
- After the match ended, the client timer kept counting.
- There is no lobby return / “play again” path yet.

These are tracked under **Deferred** in [`PLAN.md`](PLAN.md) and
[`docs/architecture.md`](docs/architecture.md).

## In progress

_Nothing actively in progress. Next work is Step 1._

## Next

**Step 1 — Request validation and WebSocket integration tests**

See the detailed approach in [`PLAN.md`](PLAN.md#current-focus).

Short checklist:

- [ ] Add pure move validator (`row`/`col`/`value` types and bounds)
- [ ] Reject unknown message types and pre-start moves
- [ ] Wire validator into `server/main.py`
- [ ] Stub or inject ML / hash HTTP for offline tests
- [ ] Unit tests for the validator
- [ ] Integration tests for join / start / move / invalid move
- [ ] Update `docs/websocket-protocol.md`
- [ ] Mark Step 1 done here and advance Current focus in `PLAN.md`

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
