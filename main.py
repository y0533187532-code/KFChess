"""Kong-Fu-Chess — board parsing, real-time moves, and command replay.

Git repo: https://github.com/y0533187532-code/KFChess

Unit-test coverage: run ``py -m pytest`` (see ``pytest.ini``); HTML report
is written to ``htmlcov/index.html``.

``main()`` only wires stdin -> ``run()`` -> stdout together (single
responsibility: orchestration). All the actual logic lives in the
``kongfu_chess`` package and is unit-tested there directly, and ``run()``
takes the raw text as a parameter (dependency injection) so tests can
call it with any string, with no need to monkeypatch sys.stdin.
"""

import sys

from kongfu_chess.app import run
from kongfu_chess.errors import BoardParsingError, InvalidPromotionTypeError

__all__ = ["main", "run"]


def main(stdin=None, stdout=None):
    """CLI entry point.

    stdin/stdout default to the real sys.stdin/sys.stdout, but can be
    replaced by the caller (e.g. an io.StringIO in tests).
    """
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout

    raw_text = stdin.read()
    try:
        run(raw_text, stdout)
    except BoardParsingError as error:
        print(f"ERROR {error.code}", file=stdout)
        sys.exit(1)
    except InvalidPromotionTypeError as error:
        print(f"ERROR {error.code}", file=stdout)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
