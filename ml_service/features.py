import statistics


def row_variance(board):
    filled_counts = [9 - row.count(0) for row in board]
    return statistics.pstdev(filled_counts)

def all_candidate_counts(board):
    counts = []
    for row in range(9):
        for col in range(9):
            if board[row][col] == 0:
                counts.append(len(possible_values(board, row, col)))
    return counts

def col_variance(board):
    counts = []
    for col in range(9):
        filled = sum(1 for row in range(9) if board[row][col] != 0)
        counts.append(filled)
    return statistics.pstdev(counts)

def count_empty(board):
    return sum(row.count(0) for row in board)

def avg_candidates(board):
    counts = all_candidate_counts(board)
    return sum(counts)/len(counts) if counts else 0


def max_candidates(board):
    counts = all_candidate_counts(board)
    return max(counts) if counts else 0


def low_candidate_cells(board):
    counts = all_candidate_counts(board)
    return sum(1 for c in counts if c <= 2)

def row_density(board):
    return sum(9 - row.count(0) for row in board) / 9


def col_density(board):
    total = 0
    for col in range(9):
        filled = sum(1 for row in range(9) if board[row][col] != 0)
        total += filled
    return total / 9


def box_density(board):
    total = 0
    for box_row in range(3):
        for box_col in range(3):
            filled = 0
            for i in range(3):
                for j in range(3):
                    if board[box_row*3 + i][box_col*3 + j] != 0:
                        filled += 1
            total += filled
    return total / 9


def possible_values(board, row, col):
    if board[row][col] != 0:
        return []

    nums = set(range(1, 10))

    # remove row
    nums -= set(board[row])

    # remove column
    nums -= {board[r][col] for r in range(9)}

    # remove box
    start_row, start_col = 3*(row//3), 3*(col//3)
    for i in range(3):
        for j in range(3):
            nums.discard(board[start_row+i][start_col+j])

    return nums
