"""Load and execute .kfc integration scripts through the public command path."""

from pathlib import Path

from kongfu_chess.game import Game
from kongfu_chess.io.board_parser import BoardParser
from kongfu_chess.texttests.script_runner import ScriptRunner

COMMAND_PREFIXES = ("click ", "wait ", "print ", "jump ", "promote ")


def _is_command_line(line):
    stripped = line.strip()
    if not stripped:
        return False
    return stripped == "print board" or stripped.startswith(COMMAND_PREFIXES)


def parse_kfc(text):
    """Parse a .kfc script into board rows, commands, and print-board expectations."""
    board_rows = []
    commands = []
    expectations = []
    section = None
    pending_expect = False

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "Board:":
            section = "board"
            continue
        if stripped == "Commands:":
            section = "commands"
            continue
        if stripped in {"Expect:", "---expect---"}:
            pending_expect = True
            continue

        if section == "board":
            board_rows.append(stripped.split())
            continue

        if section != "commands":
            continue

        if pending_expect and not _is_command_line(stripped):
            expectations[-1].append(stripped)
            continue

        pending_expect = False
        commands.append(stripped)
        if stripped == "print board":
            expectations.append([])
            pending_expect = True

    return board_rows, commands, expectations


def _split_print_outputs(stdout_text, expectation_groups):
    lines = [line for line in stdout_text.splitlines() if line.strip()]
    outputs = []
    index = 0
    for expected in expectation_groups:
        count = len(expected)
        outputs.append(lines[index : index + count])
        index += count
    return outputs


def run_kfc_script(path):
    """Execute a .kfc file and assert each print board matches its expectation block."""
    import io

    text = Path(path).read_text(encoding="utf-8")
    board_rows, commands, expectations = parse_kfc(text)

    board = BoardParser().parse_rows(board_rows)
    game = Game(board)
    stdout = io.StringIO()
    ScriptRunner(game, board, stdout).run(commands)

    outputs = _split_print_outputs(stdout.getvalue(), expectations)
    assert len(outputs) == len(expectations), (
        f"expected {len(expectations)} print board outputs, got {len(outputs)}"
    )
    for index, (actual, expected) in enumerate(zip(outputs, expectations)):
        assert actual == expected, f"print board #{index + 1}: {actual!r} != {expected!r}"
