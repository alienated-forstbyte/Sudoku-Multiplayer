import random
from engine.solver import is_valid


def generate_full_board():
    """Return a randomized, completely filled 9x9 Sudoku board.

    ``fill`` performs depth-first search in row-major order. Shuffling the
    candidate digits is what makes separate calls produce different boards.
    When a branch cannot be completed, the cell is reset before backtracking.
    """
    board = [[0 for _ in range(9)] for _ in range(9)]

    def fill():
        for row in range(9):
            for col in range(9):
                if board[row][col] == 0:
                    nums = list(range(1, 10))
                    random.shuffle(nums)

                    for num in nums:
                        if is_valid(board, row, col, num):
                            board[row][col] = num

                            if fill():
                                return True

                            board[row][col] = 0
                    return False
        return True

    fill()
    return board

def remove_numbers(board, difficulty="medium"):
    """Copy a solved board and remove clues according to a difficulty range.

    The input board is not changed. Difficulty here controls only the number
    of empty cells; this function does not prove that the resulting puzzle has
    a unique solution or measure the techniques needed to solve it.
    """
    difficulty_map = {
        "easy": (25, 35),
        "medium": (35, 45),
        "hard": (45, 60)
    }

    remove_range = difficulty_map.get(difficulty, (35, 45))
    remove_count = random.randint(*remove_range)

    puzzle = [row[:] for row in board]

    while remove_count > 0:
        row = random.randint(0, 8)
        col = random.randint(0, 8)

        if puzzle[row][col] != 0:
            puzzle[row][col] = 0
            remove_count -= 1

    return puzzle