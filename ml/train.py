import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib


# Load dataset
df = pd.read_csv("sudoku_dataset.csv")

# Features + label
X = df.drop(["difficulty", "empty_cells"], axis=1)
y = df["difficulty"]

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Model
model = RandomForestClassifier(n_estimators=100)

model.fit(X_train, y_train)

# Evaluate
y_pred = model.predict(X_test)

print(classification_report(y_test, y_pred))

# Save model
joblib.dump(model, "sudoku_model.pkl")

print("Model saved as sudoku_model.pkl")