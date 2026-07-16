from fastapi import FastAPI
import hashlib
import time

app = FastAPI()

chain = []


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


@app.post("/add")
def add_block(payload: dict):
    block = create_block(payload["data"])
    return {"hash": block["data_hash"]}


@app.post("/verify")
def verify_block(payload: dict):
    """Return whether ``payload["hash"]`` matches ``hash_data`` of the data."""
    recalculated = hash_data(payload["data"])
    return {"valid": recalculated == payload["hash"]}
