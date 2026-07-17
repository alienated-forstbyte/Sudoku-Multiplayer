import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

from ml.feature_contract import FEATURE_NAMES
from ml.model_bundle import save_model_bundle


def train_model(
    dataset_path="sudoku_dataset.csv",
    model_path="sudoku_model.pkl",
):
    """Train deterministically and save a versioned model bundle."""
    df = pd.read_csv(dataset_path)

    missing = set(FEATURE_NAMES) - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing model features: {sorted(missing)}")

    # Selecting by FEATURE_NAMES makes order explicit and excludes
    # empty_cells, which is retained in the CSV only for dataset inspection.
    X = df.loc[:, list(FEATURE_NAMES)]
    y = df["difficulty"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    report = classification_report(y_test, y_pred)
    print(report)

    save_model_bundle(model, model_path)
    print(f"Model bundle saved as {model_path}")

    return model, report


if __name__ == "__main__":
    train_model()