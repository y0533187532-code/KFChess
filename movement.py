def pixel_to_cell(x, y):
    return y // 100, x // 100


def in_bounds(board_rows, row, col):
    return 0 <= row < len(board_rows) and 0 <= col < len(board_rows[0])


def is_king_move(dr, dc):
    return max(abs(dr), abs(dc)) == 1


def is_rook_move(dr, dc):
    return (dr == 0) != (dc == 0)


def is_bishop_move(dr, dc):
    return dr != 0 and abs(dr) == abs(dc)


def is_knight_move(dr, dc):
    return {abs(dr), abs(dc)} == {1, 2}


def is_queen_move(dr, dc):
    return is_rook_move(dr, dc) or is_bishop_move(dr, dc)


MOVE_RULES = {
    "K": is_king_move,
    "R": is_rook_move,
    "B": is_bishop_move,
    "N": is_knight_move,
    "Q": is_queen_move,
}

MOVE_DURATION_MS = {
    "K": 1000,
    "Q": 1000,
    "R": 1000,
    "B": 1000,
    "N": 1000,
    "P": 1000,
}


def get_move_route(from_row, from_col, to_row, to_col, piece_type):
    if piece_type in {"N", "K", "P"}:
        return [(to_row, to_col)]

    dr = to_row - from_row
    dc = to_col - from_col
    step_r = (dr > 0) - (dr < 0)
    step_c = (dc > 0) - (dc < 0)

    route = []
    r, c = from_row + step_r, from_col + step_c
    while True:
        route.append((r, c))
        if (r, c) == (to_row, to_col):
            break
        r += step_r
        c += step_c
    return route


def is_swap_route(move_a, move_b):
    return (
        move_a["piece"][0] != move_b["piece"][0]
        and move_a["from"] == move_b["to"]
        and move_a["to"] == move_b["from"]
    )


def is_route_conflict(existing_move, new_move):
    if is_swap_route(existing_move, new_move):
        return False

    if existing_move["from"] == new_move["to"]:
        return True

    if set(existing_move["route"]) & set(new_move["route"]):
        return True

    return False


def is_same_color(piece_a, piece_b):
    return piece_a[0] == piece_b[0]


def handle_click(board_rows, selected, active_moves, x, y):
    row, col = pixel_to_cell(x, y)

    if not in_bounds(board_rows, row, col):
        return selected, active_moves

    clicked_piece = board_rows[row][col]
    moving_origins = {move["from"] for move in active_moves}

    if selected is None:
        if clicked_piece != "." and (row, col) not in moving_origins:
            selected = (row, col)
        return selected, active_moves

    sel_row, sel_col = selected
    if (sel_row, sel_col) in moving_origins:
        selected = None
        return selected, active_moves

    selected_piece = board_rows[sel_row][sel_col]

    if clicked_piece != "." and is_same_color(clicked_piece, selected_piece):
        if (row, col) in moving_origins:
            selected = None
            return selected, active_moves
        selected = (row, col)
        return selected, active_moves

    dr = row - sel_row
    dc = col - sel_col
    piece_type = selected_piece[1]

    if piece_type == "P":
        legal_move = is_pawn_move(selected_piece, clicked_piece, dr, dc)
    else:
        legal_move = MOVE_RULES[piece_type](dr, dc)

    if not legal_move:
        selected = None
        return selected, active_moves

    if piece_type in {"R", "B", "Q"}:
        if not is_path_clear(board_rows, sel_row, sel_col, row, col):
            selected = None
            return selected, active_moves

    new_route = get_move_route(sel_row, sel_col, row, col, piece_type)

    new_move = {
        "piece": selected_piece,
        "from": (sel_row, sel_col),
        "to": (row, col),
        "remaining": MOVE_DURATION_MS[piece_type],
        "order": max((move["order"] for move in active_moves), default=-1) + 1,
        "route": new_route,
    }

    for existing_move in active_moves:
        if is_route_conflict(existing_move, new_move):
            selected = None
            return selected, active_moves

    active_moves.append(new_move)
    selected = None
    return selected, active_moves


def advance_moves(board_rows, active_moves, ms):
    finished = []

    for move in active_moves:
        old_remaining = move["remaining"]
        move["remaining"] = old_remaining - ms
        if move["remaining"] <= 0:
            finished.append(
                {"move": move, "finish_time": old_remaining}
            )

    finished.sort(key=lambda item: (item["finish_time"], item["move"]["order"]))

    completed = []
    for entry in finished:
        move = entry["move"]
        if move not in active_moves:
            continue

        if not can_execute_move(move, active_moves, completed):
            active_moves.remove(move)
            continue

        from_row, from_col = move["from"]
        to_row, to_col = move["to"]

        board_rows[to_row][to_col] = move["piece"]
        board_rows[from_row][from_col] = "."

        active_moves.remove(move)
        completed.append(move)

    return active_moves


def can_execute_move(move, active_moves, completed_moves):
    for other in active_moves:
        if other is move:
            continue
        if is_swap_route(move, other) and other["order"] < move["order"]:
            return False

    for other in completed_moves:
        if is_swap_route(move, other) and other["order"] < move["order"]:
            return False

    return True


def is_path_clear(board_rows, sel_row, sel_col, row, col):
    dr = row - sel_row
    dc = col - sel_col
    step_r = (dr > 0) - (dr < 0)
    step_c = (dc > 0) - (dc < 0)

    r, c = sel_row + step_r, sel_col + step_c
    while (r, c) != (row, col):
        if board_rows[r][c] != ".":
            return False
        r += step_r
        c += step_c
    return True


def is_pawn_move(selected_piece, clicked_piece, dr, dc):
    color = selected_piece[0]

    if color == "w":
        if dc == 0 and dr == -1 and clicked_piece == ".":
            return True
        if abs(dc) == 1 and dr == -1:
            return clicked_piece != "." and clicked_piece[0] == "b"
    else:
        if dc == 0 and dr == 1 and clicked_piece == ".":
            return True
        if abs(dc) == 1 and dr == 1:
            return clicked_piece != "." and clicked_piece[0] == "w"

    return False


