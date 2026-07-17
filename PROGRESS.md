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
| ML train/serve feature parity | Complete (Step 2) |
| Environment-based configuration | Complete (Step 3) |
| Async service HTTP calls | Complete (Step 4) |
| Typed room state | Complete (Step 5) |
| Redis shared room state | Complete (Step 6) |
| Independent timeout scheduler | Next (Step 7) |
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

### Step 2 — ML training-serving feature parity

- Added one ordered, versioned feature contract in `ml/feature_contract.py`.
- Reused named DataFrames in dataset generation, training, local prediction,
  and the HTTP service.
- Added versioned model bundles with feature-name and contract validation.
- Removed the duplicate `ml_service/features.py`.
- Changed the ML-service build context so its image copies the shared `ml`
  package.
- Added deterministic dataset/training settings and ML contract tests.
- Retrained the model: 95% held-out accuracy on 600 test samples.
- Verified `/predict` returns HTTP 200 without the feature-name warning.

### Step 3 — Environment-based configuration

- Added `server/config.py` with a typed, frozen `Settings` and env parsing.
- `GameManager` reads service URLs, timeouts, room expiry, and game time limit
  from settings and accepts an injected `Settings` for tests.
- Parameterized `docker-compose.yaml` with `${VARIABLE:-default}` and added
  [`.env.example`](.env.example) plus a `.gitignore` exception for it.
- Added [`tests/test_config.py`](tests/test_config.py) covering defaults,
  overrides, invalid values, and settings injection.

### Step 4 — Async service HTTP calls

- Added one pooled `httpx.AsyncClient` owned by the FastAPI lifespan.
- Converted room creation and integrity verification to awaitable calls.
- Added separate `SERVICE_CONNECT_TIMEOUT` and `SERVICE_READ_TIMEOUT`; write
  and pool waits are also explicitly bounded.
- Removed the synchronous `requests` dependency from the game server.
- Added mock-transport tests for call flow, timeout construction, endpoint
  awaiting, non-blocking behavior, and service-failure WebSocket feedback.

### Step 5 — Typed room state

- Added `server/models.py` with `RoomState`, board aliases, connected player
  IDs, and immutable original-board copies.
- Moved room expiry, player joining/start, time remaining, timeout winner,
  move scoring, and completion logic onto the model.
- Replaced all game-server string-key state access with typed attributes.
- Fixed the obsolete `check_win_player` implementation that referenced a
  nonexistent `boards` key.
- Added focused invariant, timer, scoring, winner, and immutability tests.

### Step 6 — Redis room state and pub/sub

- Split serializable room snapshots from each worker's local WebSocket map.
- Added `InMemoryRoomRepository` / `RedisRoomRepository`; mutations use an
  async lock or distributed per-room Redis lock.
- Added in-memory and Redis event buses; every worker forwards published room
  events to its own sockets.
- Added Redis AOF persistence, configurable room TTL, and graceful player-slot
  release.
- Added serialization, concurrency, restart, and multi-manager tests.
- Live verification passed for 20 concurrent atomic mutations, two Redis
  subscribers, server restart recovery, and two players on separate workers.

### Playtest notes (not fixed yet)

- Moves and board sync worked well in a real two-player session.
- After the match ended, the client timer kept counting.
- There is no lobby return / “play again” path yet.

These are tracked under **Deferred** in [`PLAN.md`](PLAN.md) and
[`docs/architecture.md`](docs/architecture.md).

## In progress

_Nothing actively in progress. Next work is Step 7._

## Next

**Step 7 — Independent room expiry and match timeout scheduler**

See the detailed approach in [`PLAN.md`](PLAN.md#current-focus).

Short checklist:

- [ ] Store room deadlines in Redis (and an in-memory test queue)
- [ ] Add a lifespan-managed scheduler that atomically claims due work
- [ ] Expire waiting rooms without incoming messages
- [ ] Broadcast exactly one `game_over` event at match deadline
- [ ] Test duplicate workers and restart recovery

## Deferred

After the current correctness roadmap:

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
