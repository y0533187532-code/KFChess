import subprocess
import sys

from tests.conftest import PROJECT_ROOT


def test_prepare_vpl_submit_generates_layered_package():
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "prepare_vpl_submit.py")],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, result.stderr

    out = PROJECT_ROOT / "vpl_submit"
    for name in (
        "parser.py",
        "config.py",
        "errors.py",
        "piece.py",
        "board.py",
        "board_printer.py",
        "commands.py",
        "game.py",
    ):
        assert (out / name).is_file(), name

    for folder in ("rules", "engine", "realtime", "input", "model"):
        assert (out / folder).is_dir(), folder
    assert (out / "model" / "board.py").is_file()

    parser = (out / "parser.py").read_text(encoding="utf-8")
    assert "MissingPromotionChoiceError" in parser
    assert "InvalidPromotionTypeError" in parser
    assert "airborne_jump.py" in {
        path.name for path in (out / "realtime").glob("*.py")
    }
