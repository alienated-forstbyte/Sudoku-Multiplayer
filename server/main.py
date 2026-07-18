"""Game server HTTP and WebSocket endpoints.

Provides the REST API for room creation, the WebSocket protocol for
gameplay, and health/metrics endpoints for operational visibility.
"""

import json
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import prometheus_client
import redis.asyncio as redis
import structlog

from server.events import RedisEventBus
from server.game_manager import GameManager
from server.logging_config import configure_logging, correlation_id_var
from server.protocol import validate_move
from server.repository import RedisRoomRepository
from server.scheduler import RedisSchedulerBackend, TimeoutScheduler

log = structlog.get_logger(__name__)

manager = GameManager()

# ------------------------------------------------------------------
# Prometheus metrics
# ------------------------------------------------------------------

games_created = prometheus_client.Counter(
    "sudoku_games_created_total", "Total games created"
)
ws_connections = prometheus_client.Counter(
    "sudoku_ws_connections_total", "Total WebSocket connections"
)
moves_total = prometheus_client.Counter(
    "sudoku_moves_total",
    "Total move attempts",
    ["success"],
)
move_duration = prometheus_client.Histogram(
    "sudoku_move_duration_seconds", "Time to process a move"
)
service_call_duration = prometheus_client.Histogram(
    "sudoku_service_call_duration_seconds",
    "Time for upstream service calls",
    ["service"],
)
service_call_failures = prometheus_client.Counter(
    "sudoku_service_call_failures_total",
    "Upstream service call failures",
    ["service"],
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def build_http_timeout(settings) -> httpx.Timeout:
    """Build explicit connect/read/write/pool timeouts for service calls."""
    return httpx.Timeout(
        connect=settings.service_connect_timeout,
        read=settings.service_read_timeout,
        write=settings.service_read_timeout,
        pool=settings.service_connect_timeout,
    )


# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Own pooled service/Redis clients, room event subscription, and scheduler."""
    configure_logging(
        level=manager.settings.log_level,
        fmt=manager.settings.log_format,
    )
    log.info("server.startup")

    redis_client = None
    if manager.settings.redis_url:
        redis_client = redis.from_url(
            manager.settings.redis_url,
            decode_responses=True,
        )
        await redis_client.ping()
        manager.repository = RedisRoomRepository(
            redis_client,
            ttl_seconds=manager.settings.redis_room_ttl_seconds,
        )
        manager.event_bus = RedisEventBus(redis_client)
        manager.set_redis_client(redis_client)
        log.info("redis.connected", url=manager.settings.redis_url)

    scheduler = TimeoutScheduler(
        repository=manager.repository,
        event_bus=manager.event_bus,
        backend=RedisSchedulerBackend(redis_client) if redis_client else None,
        poll_interval=manager.settings.scheduler_poll_interval,
    )
    manager.scheduler = scheduler

    async with httpx.AsyncClient(
        timeout=build_http_timeout(manager.settings)
    ) as client:
        manager.http_client = client
        await manager.start()
        await scheduler.start()
        log.info("server.ready")
        try:
            yield
        finally:
            log.info("server.shutdown")
            await manager.stop()
            manager.http_client = None
            if redis_client:
                await redis_client.aclose()


# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="client"), name="static")


# ------------------------------------------------------------------
# Correlation-ID middleware
# ------------------------------------------------------------------

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or uuid4().hex[:12]
    correlation_id_var.set(cid)
    response = await call_next(request)
    response.headers["x-correlation-id"] = cid
    return response


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@app.get("/health")
async def health():
    """Health check endpoint for Docker and load balancers."""
    checks = {}
    status = "healthy"

    if manager.settings.redis_url:
        try:
            ping = await manager.redis_ping()
            if ping:
                checks["redis"] = "ok"
            else:
                checks["redis"] = "degraded"
                status = "degraded"
        except Exception:
            checks["redis"] = "unhealthy"
            status = "degraded"

    return JSONResponse({"status": status, "checks": checks})


# ------------------------------------------------------------------
# Metrics
# ------------------------------------------------------------------

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return HTMLResponse(
        prometheus_client.generate_latest(), media_type="text/plain"
    )


# ------------------------------------------------------------------
# UI
# ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    with open("client/index.html") as f:
        return f.read()


# ------------------------------------------------------------------
# WebSocket
# ------------------------------------------------------------------

@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """Run one player's side of the room WebSocket protocol.

    Clients send ``move`` messages. The server emits ``init``, ``waiting``,
    ``start``, ``update``, ``game_over``, and ``error`` events documented in
    ``docs/websocket-protocol.md``.
    """
    cid = uuid4().hex[:12]
    correlation_id_var.set(cid)
    ws_log = log.bind(correlation_id=cid, game_id=game_id)

    await websocket.accept()
    ws_connections.inc()
    ws_log.info("ws.connected")

    # Join game
    player_id, game, _started_now = await manager.join_game(
        game_id,
        websocket,
    )

    if player_id is None:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Game full, invalid, or expired"
        }))
        await websocket.close()
        ws_log.info("ws.rejected")
        return

    ws_log = ws_log.bind(player_id=player_id)

    # INIT
    await websocket.send_text(json.dumps({
        "type": "init",
        "player_id": player_id,
        "started": game.started,
        "difficulty": game.difficulty,
        "hash": game.puzzle_hash,
        "time_left": game.time_left(),
    }))

    # WAITING or START
    if not game.started:
        await websocket.send_text(json.dumps({
            "type": "waiting",
            "message": "Waiting for second player..."
        }))
    else:
        await manager.broadcast(game_id, {
            "type": "start",
            "board": game.board,
            "difficulty": game.difficulty,
            "time_left": game.time_left(),
            "message": "Game started!"
        })
        ws_log.info("game.started")

    try:
        while True:
            # Expiry and timeout checks are message-driven: receive_text below
            # waits indefinitely, so no background task closes an idle room.
            if await manager.is_expired(game_id):
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Room expired"
                }))
                await websocket.close()
                ws_log.info("ws.room_expired")
                return

            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
                continue

            game = await manager.get_game(game_id)
            if game is None:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game not found",
                }))
                continue

            # Stop if game finished
            if game.winner is not None:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game already finished"
                }))
                continue

            # Timeout check
            if await manager.check_timeout(game_id):
                game, _winner = await manager.finish_on_timeout(game_id)

                winner_text = (
                    f"Player {game.winner} wins"
                    if isinstance(game.winner, int)
                    else "Draw"
                )
                await manager.broadcast(game_id, {
                    "type": "game_over",
                    "reason": "time_up",
                    "message": f"Time's up! {winner_text}.",
                    "winner": game.winner,
                    "scores": game.scores,
                })
                ws_log.info("game.timeout", winner=game.winner)
                continue

            move, validation_error = validate_move(message)
            if validation_error:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": validation_error
                }))
                continue

            if not game.started:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Game has not started"
                }))
                continue

            # Integrity check against the immutable original puzzle hash.
            try:
                puzzle_valid = await manager.verify_puzzle(game_id)
            except Exception:
                service_call_failures.labels(service="blockchain").inc()
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Puzzle integrity service unavailable"
                }))
                ws_log.warning("integrity_check.failed")
                continue

            if not puzzle_valid:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Puzzle integrity compromised!"
                }))
                ws_log.warning("integrity_check.compromised")
                continue

            row, col, value = move
            t0 = time.monotonic()
            game, success, msg = await manager.apply_move(
                game_id,
                player_id,
                row,
                col,
                value,
            )
            move_duration.observe(time.monotonic() - t0)
            moves_total.labels(success=str(success).lower()).inc()

            response = {
                "type": "update",
                "success": success,
                "message": msg,
                "board": game.board,
                "scores": game.scores,
                "time_left": game.time_left(),
                "game_over": game.winner is not None,
                "winner": game.winner,
            }

            if game.winner is not None:
                winner_text = (
                    f"Player {game.winner} wins"
                    if isinstance(game.winner, int)
                    else "Draw"
                )
                response["reason"] = "board_complete"
                response["message"] = f"{winner_text} — board completed!"
                ws_log.info(
                    "game.completed",
                    winner=game.winner,
                    scores=game.scores,
                )

            await manager.broadcast(game_id, response)

    except WebSocketDisconnect:
        await manager.disconnect(game_id, player_id)
        ws_log.info("ws.disconnected")


# ------------------------------------------------------------------
# REST
# ------------------------------------------------------------------

@app.post("/create")
async def create_game():
    game_id = await manager.create_game()
    games_created.inc()
    log.info("game.created", game_id=game_id)
    return {"game_id": game_id}
