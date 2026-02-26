#!/usr/bin/env python3
"""
Create Desktop .command launchers for core operator workflows.
"""

from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DESKTOP = Path.home() / "Desktop"


def _launcher_specs() -> dict[str, str]:
    return {
        "Run_Permanence_Operator_Surface.command": "\n".join(
            [
                "#!/bin/zsh",
                "set -euo pipefail",
                f'cd "{BASE_DIR}"',
                'exec "./scripts/launch_operator_surface.sh" --money-loop "$@"',
            ]
        )
        + "\n",
        "Run_Permanence_Command_Center.command": "\n".join(
            [
                "#!/bin/zsh",
                "set -euo pipefail",
                f'cd "{BASE_DIR}"',
                'exec "./scripts/launch_command_center.sh" "$@"',
            ]
        )
        + "\n",
        "Run_Permanence_Foundation_Site.command": "\n".join(
            [
                "#!/bin/zsh",
                "set -euo pipefail",
                f'cd "{BASE_DIR}"',
                'exec /usr/bin/env python3 "cli.py" foundation-site "$@"',
            ]
        )
        + "\n",
        "Run_Permanence_Money_Loop.command": "\n".join(
            [
                "#!/bin/zsh",
                "set -euo pipefail",
                f'cd "{BASE_DIR}"',
                'exec /usr/bin/env bash "scripts/run_money_loop.sh"',
            ]
        )
        + "\n",
    }


def _write_launcher(path: Path, content: str, force: bool) -> str:
    if path.exists() and not force:
        return "exists"
    path.write_text(content, encoding="utf-8")
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return "written"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create Desktop launchers for Permanence workflows.")
    parser.add_argument(
        "--desktop-dir",
        default=str(DEFAULT_DESKTOP),
        help="Destination directory for .command launchers (default: ~/Desktop)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing launcher files")
    args = parser.parse_args(argv)

    desktop_dir = Path(os.path.expanduser(args.desktop_dir)).resolve()
    desktop_dir.mkdir(parents=True, exist_ok=True)

    print(f"Desktop launcher target: {desktop_dir}")
    specs = _launcher_specs()
    written = 0
    skipped = 0
    for filename, content in specs.items():
        target = desktop_dir / filename
        state = _write_launcher(target, content, force=args.force)
        if state == "written":
            written += 1
        else:
            skipped += 1
        print(f"- {filename}: {state}")

    print(f"Launchers ready. written={written} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
