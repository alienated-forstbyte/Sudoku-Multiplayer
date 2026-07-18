import random
from engine.solver import count_solutions, is_valid


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
    """Copy a solved board and remove clues while preserving a unique solution.

    Each candidate removal is tested: the clue is removed, and
    ``count_solutions`` checks whether the puzzle still has exactly one
    solution.  If removing the clue creates ambiguity, the cell is restored
    and a different cell is tried.

    ``difficulty`` controls the target number of empty cells:

    - easy: 25–35
    - medium: 35–45
    - hard: 45–60
    """
    difficulty_map = {
        "easy": (25, 35),
        "medium": (35, 45),
        "hard": (45, 60)
    }

    remove_range = difficulty_map.get(difficulty, (35, 45))
    target = random.randint(*remove_range)

    puzzle = [row[:] for row in board]
    removed = 0

    # Shuffle all cell positions so removal order is random.
    cells = [(r, c) for r in range(9) for c in range(9)]
    random.shuffle(cells)

    for row, col in cells:
        if removed >= target:
            break
        if puzzle[row][col] == 0:
            continue

        backup = puzzle[row][col]
        puzzle[row][col] = 0

        if count_solutions(puzzle, limit=2) == 1:
            removed += 1
        else:
            # Ambiguous — restore the clue.
            puzzle[row][col] = backup

    return puzzle