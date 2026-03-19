import random
from engine.solver import is_valid


def generate_full_board():
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
    difficulty_map = {
        "easy": 30,
        "medium": 40,
        "hard": 50
    }

    remove_count = difficulty_map.get(difficulty, 40)

    puzzle = [row[:] for row in board]

    while remove_count > 0:
        row = random.randint(0, 8)
        col = random.randint(0, 8)

        if puzzle[row][col] != 0:
            puzzle[row][col] = 0
            remove_count -= 1

    return puzzle