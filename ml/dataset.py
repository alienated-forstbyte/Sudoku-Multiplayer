import csv
from ml.features import *
from engine.generator import generate_full_board, remove_numbers
from ml.features import (
    count_empty,
    row_density,
    col_density,
    box_density,
    avg_candidates
)


def generate_dataset(n=1000, output="sudoku_dataset.csv"):
    data = []

    for _ in range(n):
        full = generate_full_board()

        for difficulty in ["easy", "medium", "hard"]:
            puzzle = remove_numbers(full, difficulty)

            data.append({
                "empty_cells": count_empty(puzzle),
                "row_variance": row_variance(puzzle),
                "col_variance": col_variance(puzzle),
                "row_density": row_density(puzzle),
                "col_density": col_density(puzzle),
                "box_density": box_density(puzzle),
                "avg_candidates": avg_candidates(puzzle),
                "max_candidates": max_candidates(puzzle),
                "low_candidate_cells": low_candidate_cells(puzzle),
                "difficulty": difficulty
            })
    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "empty_cells",
            "row_variance",
            "col_variance",
            "row_density",
            "col_density",
            "box_density",
            "avg_candidates",
            "max_candidates",
            "low_candidate_cells",
            "difficulty"
        ])
        writer.writeheader()
        writer.writerows(data)

    print(f"Dataset saved to {output}")


if __name__ == "__main__":
    generate_dataset(1000)