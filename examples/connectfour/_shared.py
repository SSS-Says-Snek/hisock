from __future__ import annotations

class BoardEnum:
    NO_PIECE = -1
    RED = 0
    YELLOW = 1

class Board:
    def __init__(self):
        self.board: list[list[int]] = [
            [
                BoardEnum.NO_PIECE for _ in range(7)
            ]
            for _ in range(6)
        ]
        self.win_vectors = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))

    def player_win(self, new_pos: tuple[int, int]) -> bool:
        potential_paths = []

        # Calculate potential win paths
        for win_vector in self.win_vectors:
            potential_path = []
            for i in range(4):
                new_coord = [new_pos[0] + win_vector[0] * i, new_pos[1] + win_vector[1] * i]
                if (not 0 <= new_coord[0] <= 6) or (not 0 <= new_coord[1] <= 5):
                    break
                potential_path.append(self.board[new_coord[1]][new_coord[0]])
            potential_paths.append(potential_path)

        for path in potential_paths:
            if path.count(self.board[new_pos[1]][new_pos[0]]) == 4:
                return True
        return False
