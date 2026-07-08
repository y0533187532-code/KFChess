import sys
from board_fixture import parse_board, print_board
from movement import handle_click, advance_moves


def main():
    selected = None
    active_moves = []
    lines = sys.stdin.read().splitlines()

    board_rows, commands_index = parse_board(lines)

    command_lines = lines[commands_index + 1:]

    for line in command_lines:
        if line.strip() == "":
            continue
        parts = line.split()
        cmd = parts[0]

        if cmd == "click":
            x, y = int(parts[1]), int(parts[2])
            selected, active_moves = handle_click(
                board_rows,
                selected,
                active_moves,
                x,
                y
            )
        elif cmd == "wait":
            active_moves = advance_moves(board_rows, active_moves, int(parts[1]))
        elif cmd == "print" and parts[1] == "board":
            print_board(board_rows)


if __name__ == "__main__":
    main()