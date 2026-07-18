from engine.generator import generate_full_board, remove_numbers
from engine.solver import count_solutions, solve

def is_valid_board(board):
    # Check rows
    for row in board:
        if sorted(row) != list(range(1, 10)):
            return False

    # Check columns
    for col in range(9):
        column = [board[row][col] for row in range(9)]
        if sorted(column) != list(range(1, 10)):
            return False

    # Check 3x3 grids
    for box_row in range(3):
        for box_col in range(3):
            nums = []
            for i in range(3):
                for j in range(3):
                    nums.append(board[box_row*3 + i][box_col*3 + j])
            if sorted(nums) != list(range(1, 10)):
                return False

    return True


def test_full_board_generation():
    board = generate_full_board()
    assert is_valid_board(board), "Generated board is invalid"


def test_solver_on_generated_board():
    board = generate_full_board()
    assert solve(board), "Solver failed on valid board"


def test_puzzle_solvability():
    full = generate_full_board()
    puzzle = remove_numbers(full, "medium")

    solved = [row[:] for row in puzzle]
    assert solve(solved), "Puzzle is not solvable"


def test_count_solutions_on_complete_board():
    board = generate_full_board()
    assert count_solutions(board, limit=2) == 1


def test_count_solutions_on_empty_board():
    board = [[0] * 9 for _ in range(9)]
    assert count_solutions(board, limit=2) == 2


def test_generated_puzzle_has_unique_solution_easy():
    full = generate_full_board()
    puzzle = remove_numbers(full, "easy")
    assert count_solutions(puzzle, limit=2) == 1


def test_generated_puzzle_has_unique_solution_medium():
    full = generate_full_board()
    puzzle = remove_numbers(full, "medium")
    assert count_solutions(puzzle, limit=2) == 1


def test_generated_puzzle_has_unique_solution_hard():
    full = generate_full_board()
    puzzle = remove_numbers(full, "hard")
    assert count_solutions(puzzle, limit=2) == 1


def test_remove_numbers_does_not_modify_original():
    full = generate_full_board()
    original = [row[:] for row in full]
    remove_numbers(full, "medium")
    assert full == original


def test_count_solutions_restores_board():
    full = generate_full_board()
    puzzle = remove_numbers(full, "medium")
    before = [row[:] for row in puzzle]
    count_solutions(puzzle, limit=2)
    assert puzzle == before