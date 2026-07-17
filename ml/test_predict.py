"""Manual model smoke test: ``python -m ml.test_predict``."""


def main():
    from engine.generator import generate_full_board, remove_numbers
    from ml.predict import predict_difficulty

    full = generate_full_board()
    puzzle = remove_numbers(full, "medium")

    print("Predicted:", predict_difficulty(puzzle))


if __name__ == "__main__":
    main()