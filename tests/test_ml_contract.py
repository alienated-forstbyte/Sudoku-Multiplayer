import csv
import warnings

import pytest
from fastapi.testclient import TestClient

from ml.dataset import DATASET_COLUMNS, generate_dataset
from ml.feature_contract import (
    FEATURE_NAMES,
    extract_feature_frame,
    extract_feature_record,
)
from ml.model_bundle import load_model_bundle
from ml.train import train_model
from ml_service import app as service_app


pytestmark = pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array has been deprecated.*"
)


@pytest.fixture(scope="module")
def trained_artifacts(tmp_path_factory):
    directory = tmp_path_factory.mktemp("ml-contract")
    dataset_path = directory / "dataset.csv"
    model_path = directory / "model.pkl"

    generate_dataset(n=10, output=dataset_path, random_seed=7)
    model, _report = train_model(dataset_path, model_path)

    return dataset_path, model_path, model


def test_feature_record_and_frame_use_canonical_order():
    board = [[0 for _ in range(9)] for _ in range(9)]

    record = extract_feature_record(board)
    frame = extract_feature_frame(board)

    assert tuple(record) == FEATURE_NAMES
    assert tuple(frame.columns) == FEATURE_NAMES
    assert frame.iloc[0].to_dict() == record


def test_service_imports_the_shared_extractor():
    assert service_app.extract_feature_frame is extract_feature_frame


def test_generated_dataset_uses_contract_columns(trained_artifacts):
    dataset_path, _model_path, _model = trained_artifacts

    with dataset_path.open(newline="") as dataset:
        reader = csv.DictReader(dataset)
        rows = list(reader)

    assert tuple(reader.fieldnames) == DATASET_COLUMNS
    assert len(rows) == 30


def test_model_bundle_preserves_feature_names(trained_artifacts):
    _dataset_path, model_path, trained_model = trained_artifacts

    loaded_model = load_model_bundle(model_path)

    assert tuple(trained_model.feature_names_in_) == FEATURE_NAMES
    assert tuple(loaded_model.feature_names_in_) == FEATURE_NAMES


def test_prediction_endpoint_uses_named_features_without_warning(
    trained_artifacts,
    monkeypatch,
):
    _dataset_path, model_path, _model = trained_artifacts
    monkeypatch.setattr(service_app, "MODEL_PATH", model_path)
    board = [[0 for _ in range(9)] for _ in range(9)]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with TestClient(service_app.app) as client:
            response = client.post("/predict", json={"board": board})

    assert response.status_code == 200
    assert response.json()["difficulty"] in {"easy", "medium", "hard"}
    assert not any("valid feature names" in str(item.message) for item in caught)
