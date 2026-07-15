PIECE_COLOR_INDEX = 0
PIECE_TYPE_INDEX = 1
MAX_MOVE_LOG_LINES = 8

PIECE_TYPE_NAMES = {
    "K": "King",
    "Q": "Queen",
    "R": "Rook",
    "B": "Bishop",
    "N": "Knight",
    "P": "Pawn",
}
class MoveLog:
    def __init__(self) -> None:
        self._logged_move_keys: set[tuple] = set()
        self._move_log_by_color = {
            "w": ["White"],
            "b": ["Black"],
        }

    def lines_by_color(self) -> tuple[list[str], list[str]]:
        return (
            self._move_log_by_color["w"],
            self._move_log_by_color["b"],
        )
    def _cell_name(self, row: int, col: int) -> str:
        file_letter = chr(ord("a") + col)
        rank_number = 8 - row
        return f"{file_letter}{rank_number}"

    def _piece_name(self, token: str) -> str:
        piece_type = token[PIECE_TYPE_INDEX]
        return PIECE_TYPE_NAMES.get(piece_type, token)

    def _format_move_log_line(self, token: str, move: dict, frame_index: int) -> str:
        from_row, from_col = move["from"]
        to_row, to_col = move["to"]

        seconds = frame_index / 60
        from_cell = self._cell_name(from_row, from_col)
        to_cell = self._cell_name(to_row, to_col)
        piece_name = self._piece_name(token)

        return f"{seconds:.1f}s {piece_name}: {from_cell}->{to_cell}"
        
    def record_new_moves(self, snapshot, active_moves: list[dict], frame_index: int) -> None:
        for move in active_moves:
            move_key = (
                move.get("from"),
                move.get("to"),
                move.get("order"),
            )

            if move_key in self._logged_move_keys:
                continue

            piece = self._piece_at(snapshot, move["from"])
            if piece is None:
                continue

            self._logged_move_keys.add(move_key)
            color = piece.token[PIECE_COLOR_INDEX]
            self._move_log_by_color[color].append(
                self._format_move_log_line(piece.token, move, frame_index)
            )
            self._trim_move_log(color)
            
    def _piece_at(self, snapshot, position: tuple[int, int]):
        row, col = position

        for piece in snapshot.pieces:
            if piece.row == row and piece.col == col:
                return piece

        return None

    def _trim_move_log(self, color: str) -> None:
        lines = self._move_log_by_color[color]
        header = lines[:1]
        moves_without_header = lines[1:]
        latest_moves = moves_without_header[-MAX_MOVE_LOG_LINES:]
        self._move_log_by_color[color] = header + latest_moves