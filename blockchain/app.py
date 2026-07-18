"""Blockchain integrity micro-service with health checks and Prometheus metrics."""

import hashlib
import time

import structlog
from fastapi import FastAPI, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

log = structlog.get_logger(__name__)

app = FastAPI()

chain = []

BLOCK_COUNT = Counter(
    "blockchain_blocks_total",
    "Total blocks added to the chain",
)
VERIFY_COUNT = Counter(
    "blockchain_verify_requests_total",
    "Total verify requests",
    ["result"],
)


def hash_data(data: str) -> str:
    """Return a SHA-256 hex digest of UTF-8 puzzle (or chain) payload bytes.

    Add and verify must call this same helper so integrity checks round-trip.
    """
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def create_block(data):
    """Append an in-memory block linked to the preceding chain hash.

    ``data_hash`` is the integrity value returned to the game server. The
    block's ``hash`` additionally folds in ``previous_hash`` so the in-memory
    chain remains tamper-evident for learning purposes.
    """
    previous_hash = chain[-1]["hash"] if chain else "0"
    data_hash = hash_data(data)

    block = {
        "index": len(chain),
        "timestamp": time.time(),
        "data": data,
        "previous_hash": previous_hash,
        "data_hash": data_hash,
        "hash": hash_data(f"{previous_hash}:{data_hash}"),
    }

    chain.append(block)
    return block


@app.get("/health")
def health():
    """Liveness probe — the process is up."""
    return {"status": "ok", "chain_length": len(chain)}


@app.get("/metrics")
def metrics():
    """Prometheus scrape endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/add")
def add_block(payload: dict):
    block = create_block(payload["data"])
    BLOCK_COUNT.inc()
    log.info("blockchain.block_added", index=block["index"])
    return {"hash": block["data_hash"]}


@app.post("/verify")
def verify_block(payload: dict):
    """Return whether ``payload["hash"]`` matches ``hash_data`` of the data."""
    recalculated = hash_data(payload["data"])
    valid = recalculated == payload["hash"]
    VERIFY_COUNT.labels(result="valid" if valid else "invalid").inc()
    log.info("blockchain.verify", valid=valid)
    return {"valid": valid}
