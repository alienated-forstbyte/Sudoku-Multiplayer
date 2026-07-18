def is_valid(board, row, col, num):
    """Return whether ``num`` can be placed at ``(row, col)``."""
    if num in board[row]:
        return False

    for i in range(9):
        if board[i][col] == num:
            return False

    start_row, start_col = 3 * (row // 3), 3 * (col // 3)
    for i in range(3):
        for j in range(3):
            if board[start_row + i][start_col + j] == num:
                return False

    return True


def solve(board):
    """Solve ``board`` in place with backtracking.

    Returns ``True`` once a complete solution is found. If no solution exists,
    returns ``False`` after restoring every attempted cell to zero.
    """
    for row in range(9):
        for col in range(9):
            if board[row][col] == 0:
                for num in range(1, 10):
                    if is_valid(board, row, col, num):
                        board[row][col] = num

                        if solve(board):
                            return True

                        board[row][col] = 0

                return False
    return True


def count_solutions(board, limit=2):
    """Count solutions for ``board`` up to *limit*.

    Stops early once *limit* is reached, which is sufficient to determine
    uniqueness (exactly one solution).  ``board`` is restored to its original
    state after the call.
    """
    count = [0]

    def _solve(b):
        if count[0] >= limit:
            return
        for row in range(9):
            for col in range(9):
                if b[row][col] == 0:
                    for num in range(1, 10):
                        if is_valid(b, row, col, num):
                            b[row][col] = num
                            _solve(b)
                            b[row][col] = 0
                            if count[0] >= limit:
                                return
                    return
        count[0] += 1

    _solve(board)
    return count[0]