"""ML classification micro-service with health checks and Prometheus metrics."""

import time
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Response
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from ml.feature_contract import extract_feature_frame
from ml.model_bundle import load_model_bundle

log = structlog.get_logger(__name__)

MODEL_PATH = Path(__file__).with_name("sudoku_model.pkl")
model = None

REQUEST_COUNT = Counter(
    "ml_predict_requests_total",
    "Total predict requests",
    ["status"],
)
REQUEST_LATENCY = Histogram(
    "ml_predict_latency_seconds",
    "Predict request latency in seconds",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Fail at service startup if the model bundle and code are incompatible."""
    global model
    log.info("ml_service.starting", model_path=str(MODEL_PATH))
    model = load_model_bundle(MODEL_PATH)
    log.info("ml_service.model_loaded")
    yield
    model = None
    log.info("ml_service.stopped")


app = FastAPI(lifespan=lifespan)


class BoardInput(BaseModel):
    board: list[list[int]]


@app.get("/health")
def health():
    """Liveness probe — the process is up."""
    return {"status": "ok", "model_loaded": model is not None}


@app.get("/metrics")
def metrics():
    """Prometheus scrape endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/predict")
def predict(data: BoardInput):
    if model is None:
        REQUEST_COUNT.labels(status="error").inc()
        raise RuntimeError("Model is not loaded")

    start = time.perf_counter()
    try:
        features = extract_feature_frame(data.board)
        prediction = model.predict(features)[0]
        REQUEST_COUNT.labels(status="ok").inc()
        log.info("ml.predict", difficulty=prediction)
        return {"difficulty": prediction}
    except Exception:
        REQUEST_COUNT.labels(status="error").inc()
        log.exception("ml.predict_error")
        raise
    finally:
        REQUEST_LATENCY.observe(time.perf_counter() - start)
