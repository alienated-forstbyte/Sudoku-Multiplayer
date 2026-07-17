"""Typed in-memory state and invariants for a multiplayer room."""

import time
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias


Board: TypeAlias = list[list[int]]
FrozenBoard: TypeAlias = tuple[tuple[int, ...], ...]
Winner: TypeAlias = int | Literal["draw"] | None


def freeze_board(board: Board) -> FrozenBoard:
    """Return an immutable copy suitable for integrity verification."""
    return tuple(tuple(row) for row in board)


def _validate_board(name: str, board) -> None:
    if len(board) != 9 or any(len(row) != 9 for row in board):
        raise ValueError(f"{name} must be a 9x9 board")


@dataclass
class RoomState:
    """All mutable state and core invariants for one two-player room."""

    created_at: float
    expiry_seconds: int
    board: Board
    original_board: FrozenBoard
    solution: Board
    difficulty: str
    puzzle_hash: str
    time_limit_seconds: int
    connected_player_ids: list[int] = field(default_factory=list)
    scores: dict[int, int] = field(
        default_factory=lambda: {0: 0, 1: 0}
    )
    start_time: float | None = None
    started: bool = False
    winner: Winner = None

    def __post_init__(self) -> None:
        _validate_board("board", self.board)
        _validate_board("original_board", self.original_board)
        _validate_board("solution", self.solution)
        if self.expiry_seconds <= 0:
            raise ValueError("expiry_seconds must be positive")
        if self.time_limit_seconds <= 0:
            raise ValueError("time_limit_seconds must be positive")

    def is_expired(self, now: float | None = None) -> bool:
        """Return whether an unstarted room has exceeded its wait period."""
        if self.started:
            return False
        current_time = time.time() if now is None else now
        return current_time - self.created_at > self.expiry_seconds

    def add_player(
        self,
        now: float | None = None,
    ) -> int | None:
        """Reserve a free player ID and start when both IDs are connected."""
        available = (
            player_id
            for player_id in (0, 1)
            if player_id not in self.connected_player_ids
        )
        player_id = next(available, None)
        if player_id is None:
            return None

        self.connected_player_ids.append(player_id)
        self.connected_player_ids.sort()
        self.scores[player_id] = 0

        if len(self.connected_player_ids) == 2 and not self.started:
            self.started = True
            self.start_time = time.time() if now is None else now

        return player_id

    def remove_player(self, player_id: int) -> None:
        if player_id in self.connected_player_ids:
            self.connected_player_ids.remove(player_id)

    def time_left(self, now: float | None = None) -> int:
        if self.start_time is None:
            return self.time_limit_seconds

        current_time = time.time() if now is None else now
        remaining = self.time_limit_seconds - (
            current_time - self.start_time
        )
        return max(0, int(remaining))

    def is_timed_out(self, now: float | None = None) -> bool:
        return self.time_left(now) <= 0

    def finish_on_timeout(self) -> Winner:
        """Set and return the score-based winner after a timeout."""
        if self.scores[0] > self.scores[1]:
            self.winner = 0
        elif self.scores[1] > self.scores[0]:
            self.winner = 1
        else:
            self.winner = "draw"
        return self.winner

    def is_complete(self) -> bool:
        return all(0 not in row for row in self.board)

    def apply_move(
        self,
        player_id: int,
        row: int,
        col: int,
        value: int,
    ) -> tuple[bool, str]:
        """Apply one validated move and update score/winner if correct."""
        if self.board[row][col] != 0:
            return False, "Cell already filled"

        if self.solution[row][col] != value:
            return False, "Incorrect move"

        self.board[row][col] = value
        self.scores[player_id] += 1
        if self.is_complete():
            self.winner = player_id

        return True, "Correct move"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot for a shared state repository."""
        return {
            "created_at": self.created_at,
            "expiry_seconds": self.expiry_seconds,
            "board": self.board,
            "original_board": [list(row) for row in self.original_board],
            "solution": self.solution,
            "difficulty": self.difficulty,
            "puzzle_hash": self.puzzle_hash,
            "time_limit_seconds": self.time_limit_seconds,
            "connected_player_ids": self.connected_player_ids,
            "scores": self.scores,
            "start_time": self.start_time,
            "started": self.started,
            "winner": self.winner,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoomState":
        """Restore a snapshot, normalizing JSON string score keys."""
        return cls(
            created_at=data["created_at"],
            expiry_seconds=data["expiry_seconds"],
            board=data["board"],
            original_board=freeze_board(data["original_board"]),
            solution=data["solution"],
            difficulty=data["difficulty"],
            puzzle_hash=data["puzzle_hash"],
            time_limit_seconds=data["time_limit_seconds"],
            connected_player_ids=list(data.get("connected_player_ids", [])),
            scores={
                int(player_id): score
                for player_id, score in data.get(
                    "scores", {0: 0, 1: 0}
                ).items()
            },
            start_time=data.get("start_time"),
            started=data.get("started", False),
            winner=data.get("winner"),
        )
