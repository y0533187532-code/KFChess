import subprocess
import sys

import pytest

from tests.conftest import PROJECT_ROOT

VPL_DIR = PROJECT_ROOT / "vpl_submit"
PARSER_PY = VPL_DIR / "parser.py"


@pytest.fixture(scope="module", autouse=True)
def regenerate_vpl_submit():
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "prepare_vpl_submit.py")],
        check=True,
        cwd=str(PROJECT_ROOT),
    )


def test_vpl_parser_prints_board_after_king_move():
    raw_text = (
        "Board:\n"
        "wK . .\n"
        ". . .\n"
        ". . .\n"
        "Commands:\n"
        "click 50 50\n"
        "click 150 150\n"
        "wait 1000\n"
        "print board\n"
    )
    result = subprocess.run(
        [sys.executable, str(PARSER_PY)],
        input=raw_text,
        capture_output=True,
        text=True,
        cwd=str(VPL_DIR),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [". . .", ". wK .", ". . ."]


def test_vpl_parser_reports_unknown_token_error():
    raw_text = "Board:\nwK xZ\n. .\nCommands:\n"
    result = subprocess.run(
        [sys.executable, str(PARSER_PY)],
        input=raw_text,
        capture_output=True,
        text=True,
        cwd=str(VPL_DIR),
    )
    assert result.returncode == 1
    assert result.stdout.strip() == "ERROR UNKNOWN_TOKEN"
