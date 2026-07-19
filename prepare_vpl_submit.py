"""Copy project files into vpl_submit/ for uploading to VPL.

VPL runs main.py at the upload root (not as a package). Upload the entire
vpl_submit/ folder contents to VPL, keeping the rules/ subfolder.
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
    ("piece_state.py", PKG / "model" / "piece_state.py"),
    ("board.py", PKG / "model" / "board.py"),
    ("commands.py", PKG / "texttests" / "script_runner.py"),
    ("game.py", PKG / "game.py"),
]

RULES_FILES = [
    "__init__.py",
    "shapes.py",
    "pawn.py",
    "path.py",
    "routes.py",
    "piece_rules.py",
    "rule_engine.py",
    "promotion.py",
]

VPL_MAIN = '''\
"""VPL entry point — flat imports, same behavior as repo root main.py."""

import sys

from board import Board
from commands import ScriptRunner
from errors import (
    BoardParsingError,
    InvalidPromotionTypeError,
    MissingPromotionChoiceError,
)
from game import Game
from parser import InputParser


def main(stdin=None, stdout=None):
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout

    raw_text = stdin.read()
    try:
        parser = InputParser()
        board_rows, command_lines = parser.parse(raw_text)
        board = Board(board_rows)
        game = Game(board)
        ScriptRunner(game, board, stdout).run(command_lines)
    except BoardParsingError as error:
        print(f"ERROR {error.code}", file=stdout)
        sys.exit(1)
    except InvalidPromotionTypeError as error:
        print(f"ERROR {error.code}", file=stdout)
        sys.exit(1)
    except MissingPromotionChoiceError as error:
        print(f"ERROR {error.code}", file=stdout)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    script_parser = (PKG / "texttests" / "script_parser.py").read_text(encoding="utf-8")
    parser_body = script_parser.split("class ScriptParser")[0].rstrip()
    (OUT / "parser.py").write_text(parser_body + "\n", encoding="utf-8")
    (OUT / "main.py").write_text(VPL_MAIN, encoding="utf-8")

    for dest_name, src_path in FLAT_FILES:
        shutil.copy2(src_path, OUT / dest_name)

    rules_out = OUT / "rules"
    rules_out.mkdir()
    for name in RULES_FILES:
        shutil.copy2(PKG / "rules" / name, rules_out / name)

    engine_out = OUT / "engine"
    engine_out.mkdir()
    for name in (
        "__init__.py",
        "capture_service.py",
        "event_bus.py",
        "game_engine.py",
        "motion_outcome_handler.py",
        "ports.py",
        "reasons.py",
        "settings.py",
        "snapshot_builder.py",
        "types.py",
    ):
        shutil.copy2(PKG / "engine" / name, engine_out / name)

    realtime_out = OUT / "realtime"
    realtime_out.mkdir()
    for name in (
        "__init__.py",
        "motion.py",
        "collision.py",
        "real_time_arbiter.py",
        "arrival_resolver.py",
        "airborne_jump.py",
    ):
        shutil.copy2(PKG / "realtime" / name, realtime_out / name)

    input_out = OUT / "input"
    input_out.mkdir()
    for name in ("__init__.py", "board_mapper.py", "controller.py"):
        shutil.copy2(PKG / "input" / name, input_out / name)

    model_out = OUT / "model"
    model_out.mkdir()
    for name in (
        "__init__.py",
        "board.py",
        "captured_piece.py",
        "events.py",
        "game_state.py",
        "move_history.py",
        "piece.py",
        "piece_state.py",
        "position.py",
    ):
        shutil.copy2(PKG / "model" / name, model_out / name)

    shutil.copy2(PKG / "io" / "board_printer.py", OUT / "board_printer.py")

    print(f"Created {OUT}")
    print("Upload the entire vpl_submit/ folder to VPL.")
    print("VPL executes main.py. Required files:")
    print("  main.py, parser.py, config.py, errors.py, piece.py, board.py, board_printer.py,")
    print("  commands.py, game.py, rules/, engine/, input/, model/, realtime/")


if __name__ == "__main__":
    main()
