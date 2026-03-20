from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import json

from features import (
    row_density, col_density, box_density,
    avg_candidates,
    count_empty,
    max_candidates,
    low_candidate_cells,
    row_variance
)

app = FastAPI()

model = joblib.load("sudoku_model.pkl")


class BoardInput(BaseModel):
    board: list


def extract_features(board):
    return [[
        row_density(board),
        col_density(board),
        box_density(board),
        avg_candidates(board),
        count_empty(board),
        max_candidates(board),
        low_candidate_cells(board),
        row_variance(board)
    ]]


@app.post("/predict")
def predict(data: BoardInput):
    board = data.board
    features = extract_features(board)

    prediction = model.predict(features)[0]

    return {"difficulty": prediction}