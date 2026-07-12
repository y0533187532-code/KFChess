"""Copy project files into vpl_submit/ for uploading to VPL.

VPL runs parser.py as a script (not as part of a package). Upload the
entire vpl_submit/ folder contents to VPL, keeping the movement/ subfolder.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "kongfu_chess"
OUT = ROOT / "vpl_submit"

FLAT_FILES = [
    ("config.py", PKG / "config.py"),
    ("errors.py", PKG / "errors.py"),
    ("piece.py", PKG / "model" / "piece.py"),
    ("board.py", PKG / "model" / "board.py"),
    ("commands.py", PKG / "texttests" / "script_runner.py"),
    ("game.py", PKG / "game.py"),
]

MOVEMENT_FILES = [
    "__init__.py",
    "pawn.py",
    "path.py",
    "routes.py",
    "rules.py",
    "shapes.py",
]

PARSER_MAIN = '''\
if __name__ == "__main__":
    import sys

    try:
        from .board import Board
        from .commands import ScriptRunner
        from .errors import BoardParsingError
        from .game import Game
    except ImportError:
        from board import Board
        from commands import ScriptRunner
        from errors import BoardParsingError
        from game import Game

    _stdin = sys.stdin
    _stdout = sys.stdout
    _raw_text = _stdin.read()
    try:
        _parser = InputParser()
        _board_rows, _command_lines = _parser.parse(_raw_text)
        _board = Board(_board_rows)
        _game = Game(_board)
        ScriptRunner(_game, _board, _stdout).run(_command_lines)
    except BoardParsingError as _error:
        print(f"ERROR {_error.code}", file=_stdout)
        sys.exit(1)
'''


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    script_parser = (PKG / "texttests" / "script_parser.py").read_text(encoding="utf-8")
    parser_body = script_parser.split("class ScriptParser")[0].rstrip()
    (OUT / "parser.py").write_text(parser_body + "\n\n" + PARSER_MAIN, encoding="utf-8")

    for dest_name, src_path in FLAT_FILES:
        shutil.copy2(src_path, OUT / dest_name)

    movement_out = OUT / "movement"
    movement_out.mkdir()
    for name in MOVEMENT_FILES:
        shutil.copy2(PKG / "movement" / name, movement_out / name)

    input_out = OUT / "input"
    input_out.mkdir()
    for name in ("__init__.py", "board_mapper.py", "controller.py"):
        shutil.copy2(PKG / "input" / name, input_out / name)

    model_out = OUT / "model"
    model_out.mkdir()
    for name in ("__init__.py", "position.py", "game_state.py"):
        shutil.copy2(PKG / "model" / name, model_out / name)

    print(f"Created {OUT}")
    print("Upload these files to VPL:")
    print("  parser.py, config.py, errors.py, piece.py, board.py,")
    print("  commands.py, game.py, movement/, input/, model/")


if __name__ == "__main__":
    main()
