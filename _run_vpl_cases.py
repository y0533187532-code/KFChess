import re
import subprocess
import sys
from pathlib import Path

CASES_FILE = Path(r"c:\Users\User\Downloads\vpl_evaluate.cases")
MAIN_PY = Path(__file__).resolve().parent / "main.py"


def parse_cases(text):
    blocks = re.split(r"\n(?=Case = )", text.strip())
    cases = []
    for block in blocks:
        match_name = re.match(r"Case = (\S+)", block)
        if not match_name:
            continue
        name = match_name.group(1)
        match_input = re.search(r"Input =\s*(.*?)\nOutput =", block, re.DOTALL)
        match_output = re.search(r"Output =\s*(.*)\Z", block, re.DOTALL)
        if not match_input or not match_output:
            cases.append((name, None, None))
            continue
        inp = match_input.group(1).rstrip("\n")
        out_raw = match_output.group(1).strip()
        if out_raw.startswith('"') and out_raw.endswith('"'):
            out_raw = out_raw[1:-1]
        expected = out_raw.replace("\\n", "\n").strip()
        cases.append((name, inp, expected))
    return cases


def run_case(name, inp, expected):
    result = subprocess.run(
        [sys.executable, str(MAIN_PY)],
        input=inp,
        capture_output=True,
        text=True,
        cwd=str(MAIN_PY.parent),
    )
    actual = result.stdout.strip()
    ok = actual == expected
    return ok, actual, result.returncode, result.stderr


def main():
    text = CASES_FILE.read_text(encoding="utf-8")
    cases = parse_cases(text)
    passed = []
    failed = []

    for name, inp, expected in cases:
        if inp is None:
            failed.append((name, "PARSE_FAIL", "", ""))
            continue
        ok, actual, exit_code, stderr = run_case(name, inp, expected)
        if ok:
            passed.append(name)
        else:
            failed.append((name, expected, actual, exit_code, stderr))

    print(f"Total: {len(cases)}, Passed: {len(passed)}, Failed: {len(failed)}")
    for name, expected, actual, exit_code, stderr in failed:
        print(f"\nFAIL {name} (exit={exit_code})")
        print(f"  expected: {expected!r}")
        print(f"  actual:   {actual!r}")
        if stderr.strip():
            print(f"  stderr:   {stderr.strip()!r}")


if __name__ == "__main__":
    main()
