"""Versioned feature contract shared by training and model serving."""

from ml.features import (
    avg_candidates,
    box_density,
    col_density,
    col_variance,
    low_candidate_cells,
    max_candidates,
    row_density,
    row_variance,
)


FEATURE_CONTRACT_VERSION = 1

# Order is part of the model API. Never reorder this tuple without incrementing
# FEATURE_CONTRACT_VERSION and retraining the model.
FEATURE_NAMES = (
    "row_variance",
    "col_variance",
    "row_density",
    "col_density",
    "box_density",
    "avg_candidates",
    "max_candidates",
    "low_candidate_cells",
)

FEATURE_FUNCTIONS = (
    row_variance,
    col_variance,
    row_density,
    col_density,
    box_density,
    avg_candidates,
    max_candidates,
    low_candidate_cells,
)


def extract_feature_record(board) -> dict[str, float]:
    """Return one named feature record in canonical contract order."""
    return {
        name: function(board)
        for name, function in zip(FEATURE_NAMES, FEATURE_FUNCTIONS)
    }


def extract_feature_frame(board):
    """Return a one-row DataFrame with the names/order used during training."""
    import pandas as pd

    return pd.DataFrame(
        [extract_feature_record(board)],
        columns=FEATURE_NAMES,
    )
