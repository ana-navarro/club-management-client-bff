"""Run the tests and require 90% line coverage, leaving out files marked @wip."""

import subprocess
import sys
from pathlib import Path

MINIMUM_COVERAGE = "90"


def main() -> int:
    wip = [str(p) for p in Path("src").rglob("*.py") if "@wip" in p.read_text(encoding="utf-8")]
    omit = [f"--omit={','.join(wip)}"] if wip else []
    run = [sys.executable, "-m", "coverage", "run", *omit, "-m", "pytest"]
    tests = subprocess.run(run, check=False)
    if tests.returncode != 0:
        return tests.returncode
    report = [sys.executable, "-m", "coverage", "report", *omit, f"--fail-under={MINIMUM_COVERAGE}"]
    return subprocess.run(report, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
