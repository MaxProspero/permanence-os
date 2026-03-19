#!/usr/bin/env python3
"""Post-bash hook: remind about test runs after code modifications.

Checks if recently modified .py files in scripts/ have corresponding tests.
Lightweight check -- does not run tests, just flags coverage gaps.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BASE_DIR / "scripts"
TESTS_DIR = BASE_DIR / "tests"


def check_test_coverage():
    """Check if scripts have corresponding test files."""
    missing = []
    if not SCRIPTS_DIR.exists() or not TESTS_DIR.exists():
        return missing

    for script in SCRIPTS_DIR.glob("*.py"):
        if script.name.startswith("_") or script.name == "__init__.py":
            continue
        test_name = f"test_{script.stem}.py"
        test_path = TESTS_DIR / test_name
        if not test_path.exists():
            missing.append(script.name)

    return missing


def main():
    missing = check_test_coverage()
    if missing and len(missing) <= 20:
        # Only report if a manageable number -- avoid noise
        print(f"Scripts without test files ({len(missing)}):")
        for name in sorted(missing)[:10]:
            print(f"  scripts/{name} -> tests/test_{name}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
    sys.exit(0)  # Always exit 0 -- this is informational only


if __name__ == "__main__":
    main()
