"""Copy project files into vpl_submit/ for uploading to VPL.

VPL runs parser.py as a script (not as part of a package). Upload the
entire vpl_submit/ folder contents to VPL, keeping the movement/ subfolder.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "vpl_submit"

FLAT_FILES = [
    "config.py",
    "errors.py",
    "piece.py",
    "board.py",
    "commands.py",
    "game.py",
]

MOVEMENT_FILES = [
    "__init__.py",
    "pawn.py",
    "path.py",
    "routes.py",
    "rules.py",
    "shapes.py",
]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    shutil.copy2(ROOT / "kongfu_chess" / "parser.py", OUT / "parser.py")

    for name in FLAT_FILES:
        shutil.copy2(ROOT / "kongfu_chess" / name, OUT / name)

    movement_out = OUT / "movement"
    movement_out.mkdir()
    for name in MOVEMENT_FILES:
        shutil.copy2(ROOT / "kongfu_chess" / "movement" / name, movement_out / name)

    print(f"Created {OUT}")
    print("Upload these files to VPL:")
    print("  parser.py, config.py, errors.py, piece.py, board.py,")
    print("  commands.py, game.py, movement/ (entire folder)")


if __name__ == "__main__":
    main()
