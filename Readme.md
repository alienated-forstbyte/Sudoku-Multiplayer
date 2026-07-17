# Multiplayer Sudoku MLOps Demo

A learning project that connects a browser-based multiplayer Sudoku game to a
FastAPI WebSocket server, a scikit-learn inference service, a small hash-chain
service, and a self-hosted Matomo analytics stack.

The project is a prototype rather than a production-ready system. Its value is
in showing how game logic, real-time communication, model serving, containers,
and analytics fit together.

## What the game does

- Creates rooms with unique IDs.
- Starts a game when two players have connected.
- Gives both players the same shared Sudoku board.
- Validates moves on the server against the generated solution.
- Awards one point to the player who fills a cell correctly.
- Ends when the board is complete or, after a client message triggers the
  timeout check, when the 10-minute limit has elapsed.
- Calls a separate ML API to label each generated puzzle.
- Records puzzle data in an in-memory hash chain.

Because the board is shared, a correct move immediately appears for both
players. The player who submits the final correct value wins; on timeout, the
highest score wins.

## Architecture

```text
Browser
  ├── HTTP POST /create ───────────────┐
  └── WebSocket /ws/{game_id} ─────────┤
                                       ▼
                              FastAPI game server
                                ├── Sudoku engine
                                ├── in-memory rooms
                                ├── HTTP ──► ML service
                                └── HTTP ──► hash-chain service

Browser analytics ──► Matomo ──► MariaDB
                  └─► Microsoft Clarity
```

See [docs/architecture.md](docs/architecture.md) for the request flow, state
model, service boundaries, and design trade-offs. See
[docs/websocket-protocol.md](docs/websocket-protocol.md) for the real-time
message format. Track work in [PLAN.md](PLAN.md) and [PROGRESS.md](PROGRESS.md).

## Project structure

```text
.
├── blockchain/       # In-memory hash-chain FastAPI service
├── client/           # HTML, CSS, and browser WebSocket client
├── engine/           # Sudoku generation, validation, and solving
├── ml/               # Dataset generation, feature code, training, inference
├── ml_service/       # Standalone model-serving FastAPI service
├── server/           # Game API, WebSocket protocol, and room state
├── tests/            # Sudoku engine tests
├── Dockerfile        # Game-server image
└── docker-compose.yaml
```

## Prerequisites

- Docker Engine with Docker Compose v2
- Python 3.11+ if you want to train or test locally
- `websocat` (optional) for inspecting WebSocket messages from a terminal

## Quick start

The `Makefile` wraps the whole workflow. From a clean clone:

```bash
make all        # install deps, generate data, train, then compose up
```

Other useful targets (`make help` lists them all):

```bash
make train        # (re)train and place the model in both locations
make test         # run the test suite in a local venv
make up-detached  # build and start the stack in the background
make logs         # follow application service logs
make down         # stop the stack
make clean        # stop, drop volumes, and remove generated artifacts
```

If `make` is unavailable, `./run.sh` provides the same steps
(`./run.sh all|install|train|test|up|down|clean`).

## Prepare the ML artifact manually

The targets above handle this for you. To do it by hand instead: model and
dataset files are intentionally ignored by Git, so a fresh clone does not
contain `sudoku_model.pkl`.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python -m ml.dataset
python -m ml.train
cp sudoku_model.pkl ml_service/sudoku_model.pkl
```

The root model supports local prediction; the copied model is loaded by the ML
service. Both are versioned bundles containing the estimator, ordered feature
names, contract version, and training scikit-learn version. Training and
serving share `ml/feature_contract.py`, and service startup rejects an
incompatible artifact.

## Run with Docker Compose

```bash
docker compose up --build
```

Services:

- Game UI and API: http://localhost:8000
- ML difficulty service: http://localhost:8001
- Puzzle hash-chain service: http://localhost:8002
- Matomo analytics UI: http://localhost:8081

Open http://localhost:8000, create a room, copy its ID into a second browser
window, and join from that window.

## Configuration

All runtime settings have development defaults, so the stack runs with no
configuration. To override them, copy the example file and edit values; Docker
Compose loads `.env` automatically:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `ML_SERVICE_URL` | `http://ml_service:8001` | Difficulty service base URL |
| `BLOCKCHAIN_SERVICE_URL` | `http://blockchain:8002` | Hash-chain service base URL |
| `SERVICE_CONNECT_TIMEOUT` | `2` | Seconds allowed to establish a connection |
| `SERVICE_READ_TIMEOUT` | `5` | Seconds allowed to wait for a response |
| `ROOM_EXPIRY_SECONDS` | `25` | Waiting-room lifetime before a second player |
| `GAME_TIME_LIMIT_SECONDS` | `600` | Match duration before timeout scoring |
| `MATOMO_DB_ROOT_PASSWORD` | `rootpassword` | MariaDB root password |
| `MATOMO_DB_NAME` | `matomo` | Matomo database name |
| `MATOMO_DB_USER` | `matomo` | Matomo database user |
| `MATOMO_DB_PASSWORD` | `matomo_password` | Matomo database password |

The database credentials are development defaults. Change them in `.env` before
exposing the stack beyond local development.

## Inspect the APIs

Create a room:

```bash
curl -X POST http://localhost:8000/create
```

Connect to it:

```bash
websocat ws://localhost:8000/ws/<game_id>
```

Send a move:

```json
{"type":"move","row":0,"col":1,"value":7}
```

FastAPI also exposes interactive API documentation at:

- http://localhost:8000/docs
- http://localhost:8001/docs
- http://localhost:8002/docs

## Run tests

From the repository root:

```bash
python -m pip install pytest
python -m pytest -q
python -m compileall engine server ml ml_service blockchain
docker compose config --quiet
```

The tests cover board generation/solving, hash verification, WebSocket
validation and broadcasts, and ML training-serving feature parity.

## Important prototype limitations

- Rooms, players, scores, the hash chain, and timers live only in process
  memory. Restarting a service loses its state, and multiple game-server
  workers would not share rooms.
- Puzzle difficulty starts as a clue-removal range; the generator does not
  prove that a puzzle has exactly one solution.
- Timeout handling is message-driven, not scheduled in the background.
- Service URLs, timeouts, and game timing come from environment variables that
  default to Docker DNS names; running only the game server directly on the
  host still requires setting `ML_SERVICE_URL` and `BLOCKCHAIN_SERVICE_URL`.
- Network/service errors are not yet handled gracefully by room creation.
- Analytics scripts send browser usage data; review consent, retention, and
  privacy requirements before deployment.

These are useful next improvements because they cross the boundaries between
application logic, distributed state, model reproducibility, and operations.

## Learning path

1. Start with `engine/generator.py` and `engine/solver.py` to understand
   backtracking.
2. Read `server/game_manager.py` to see how room state is represented.
3. Follow `server/main.py` and
   [docs/websocket-protocol.md](docs/websocket-protocol.md) for multiplayer
   events.
4. Compare `ml/dataset.py`, `ml/train.py`, and `ml_service/app.py` to learn why
   training-serving feature parity matters.
5. Inspect `docker-compose.yaml` to see how service names become internal DNS
   names on a Compose network.

## Technology

- Python, FastAPI, Uvicorn, WebSockets
- scikit-learn Random Forest, pandas, joblib
- HTML, CSS, and vanilla JavaScript
- Docker and Docker Compose
- Matomo, MariaDB, and Microsoft Clarity