import csv
import random

from engine.generator import generate_full_board, remove_numbers
from ml.feature_contract import FEATURE_NAMES, extract_feature_record
from ml.features import count_empty


DATASET_COLUMNS = (
    "empty_cells",
    *FEATURE_NAMES,
    "difficulty",
)


def generate_dataset(n=1000, output="sudoku_dataset.csv", random_seed=42):
    """Generate deterministic synthetic puzzles using the shared contract."""
    random.seed(random_seed)
    data = []

    for _ in range(n):
        full = generate_full_board()

        for difficulty in ["easy", "medium", "hard"]:
            puzzle = remove_numbers(full, difficulty)

            record = {
                "empty_cells": count_empty(puzzle),
                **extract_feature_record(puzzle),
                "difficulty": difficulty,
            }
            data.append(record)

    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        writer.writerows(data)

    print(f"Dataset saved to {output}")


if __name__ == "__main__":
    generate_dataset(1000)