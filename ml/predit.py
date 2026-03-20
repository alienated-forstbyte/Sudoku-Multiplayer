import joblib
from ml.features import *


model = joblib.load("sudoku_model.pkl")


def extract_features(board):
    return [[
        row_variance(board),
        col_variance(board),
        row_density(board),
        col_density(board),
        box_density(board),
        avg_candidates(board),
        max_candidates(board),
        low_candidate_cells(board)
    ]]


def predict_difficulty(board):
    features = extract_features(board)
    return model.predict(features)[0]