from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from ml.feature_contract import extract_feature_frame
from ml.model_bundle import load_model_bundle


MODEL_PATH = Path(__file__).with_name("sudoku_model.pkl")
model = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Fail at service startup if the model bundle and code are incompatible."""
    global model
    model = load_model_bundle(MODEL_PATH)
    yield
    model = None


app = FastAPI(lifespan=lifespan)


class BoardInput(BaseModel):
    board: list[list[int]]


@app.post("/predict")
def predict(data: BoardInput):
    if model is None:
        raise RuntimeError("Model is not loaded")

    features = extract_feature_frame(data.board)
    prediction = model.predict(features)[0]

    return {"difficulty": prediction}