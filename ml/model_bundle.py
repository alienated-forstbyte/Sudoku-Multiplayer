"""Save and load model artifacts together with their feature metadata."""

from pathlib import Path

import joblib
import sklearn

from ml.feature_contract import FEATURE_CONTRACT_VERSION, FEATURE_NAMES


MODEL_BUNDLE_VERSION = 1


def save_model_bundle(model, path) -> None:
    """Persist a model with enough metadata to validate serving compatibility."""
    artifact = {
        "bundle_version": MODEL_BUNDLE_VERSION,
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "sklearn_version": sklearn.__version__,
        "model": model,
    }
    joblib.dump(artifact, Path(path))


def load_model_bundle(path):
    """Load a model only if its metadata matches the current feature contract."""
    artifact = joblib.load(Path(path))

    if not isinstance(artifact, dict) or "model" not in artifact:
        raise ValueError(
            "Legacy model artifact detected; retrain it with `make train`."
        )

    if artifact.get("bundle_version") != MODEL_BUNDLE_VERSION:
        raise ValueError("Unsupported model bundle version")

    if artifact.get("feature_contract_version") != FEATURE_CONTRACT_VERSION:
        raise ValueError("Model feature contract version does not match code")

    if artifact.get("feature_names") != list(FEATURE_NAMES):
        raise ValueError("Model feature names or order do not match code")

    return artifact["model"]
