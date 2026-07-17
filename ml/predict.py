from ml.feature_contract import extract_feature_frame
from ml.model_bundle import load_model_bundle


model = load_model_bundle("sudoku_model.pkl")


def predict_difficulty(board):
    features = extract_feature_frame(board)
    return model.predict(features)[0]