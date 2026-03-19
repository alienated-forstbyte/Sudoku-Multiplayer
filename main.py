from engine.generator import generate_full_board, remove_numbers

def print_board(board):
    for row in board:
        print(row)


if __name__ == "__main__":
    full = generate_full_board()
    puzzle = remove_numbers(full, "medium")

    print("Generated Sudoku:\n")
    print_board(puzzle)