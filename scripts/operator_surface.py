#!/usr/bin/env python3
"""
Run the visible operator surface in one command.

Starts:
- Dashboard API / Command Center
- FOUNDATION landing page

Optionally runs a money-loop refresh before boot.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional, Sequence

BASE_DIR = Path(__file__).resolve().parents[1]


def _python_bin() -> str:
    venv_python = BASE_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _open_urls(urls: Sequence[str], delay_seconds: float = 1.0) -> None:
    time.sleep(delay_seconds)
    for url in urls:
        webbrowser.open_new_tab(url)


def _build_command_center_cmd(args: argparse.Namespace, python_bin: str) -> list[str]:
    cmd = [
        python_bin,
        str(BASE_DIR / "scripts" / "command_center.py"),
        "--host",
        args.host,
        "--port",
        str(args.dashboard_port),
        "--no-open",
    ]
    if args.run_horizon:
        cmd.append("--run-horizon")
    if args.demo_horizon:
        cmd.append("--demo-horizon")
    return cmd


def _build_foundation_site_cmd(args: argparse.Namespace, python_bin: str) -> list[str]:
    return [
        python_bin,
        str(BASE_DIR / "scripts" / "foundation_site.py"),
        "--host",
        args.host,
        "--port",
        str(args.foundation_port),
        "--no-open",
    ]


def _shutdown_processes(processes: list[tuple[str, subprocess.Popen]]) -> None:
    for _name, proc in processes:
        if proc.poll() is None:
            proc.terminate()

    deadline = time.time() + 5
    while time.time() < deadline:
        if all(proc.poll() is not None for _, proc in processes):
            return
        time.sleep(0.1)

    for _name, proc in processes:
        if proc.poll() is None:
            proc.kill()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Start command center + FOUNDATION site together.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for both services")
    parser.add_argument("--dashboard-port", type=int, default=8000, help="Dashboard API port")
    parser.add_argument("--foundation-port", type=int, default=8787, help="FOUNDATION site port")
    parser.add_argument("--no-open", action="store_true", help="Do not auto-open browser tabs")
    parser.add_argument("--money-loop", action="store_true", help="Run one money-loop refresh before launch")
    parser.add_argument("--run-horizon", action="store_true", help="Run Horizon agent before dashboard boot")
    parser.add_argument(
        "--demo-horizon",
        action="store_true",
        help="Use deterministic Horizon demo mode (requires --run-horizon)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print commands and exit")
    args = parser.parse_args(argv)

    if args.demo_horizon and not args.run_horizon:
        parser.error("--demo-horizon requires --run-horizon")

    python_bin = _python_bin()
    money_loop_cmd = [python_bin, str(BASE_DIR / "cli.py"), "money-loop"]
    command_center_cmd = _build_command_center_cmd(args, python_bin)
    foundation_cmd = _build_foundation_site_cmd(args, python_bin)

    if args.dry_run:
        print(f"[dry-run] money-loop: {' '.join(money_loop_cmd)}")
        print(f"[dry-run] command-center: {' '.join(command_center_cmd)}")
        print(f"[dry-run] foundation-site: {' '.join(foundation_cmd)}")
        return 0

    if args.money_loop:
        print(f"[operator-surface] Running money loop: {' '.join(money_loop_cmd)}")
        loop_rc = subprocess.call(money_loop_cmd, cwd=str(BASE_DIR))
        if loop_rc != 0:
            print(f"[operator-surface] money-loop failed with code {loop_rc}")
            return loop_rc

    dashboard_url = f"http://{args.host}:{args.dashboard_port}"
    foundation_url = f"http://{args.host}:{args.foundation_port}/"
    print(f"[operator-surface] Starting dashboard: {dashboard_url}")
    print(f"[operator-surface] Starting FOUNDATION site: {foundation_url}")

    processes: list[tuple[str, subprocess.Popen]] = []
    env = os.environ.copy()
    env["PERMANENCE_BASE_DIR"] = str(BASE_DIR)
    dashboard_proc = subprocess.Popen(command_center_cmd, cwd=str(BASE_DIR), env=env)
    processes.append(("command-center", dashboard_proc))
    foundation_proc = subprocess.Popen(foundation_cmd, cwd=str(BASE_DIR), env=env)
    processes.append(("foundation-site", foundation_proc))

    def _signal_handler(_sig: int, _frame: object) -> None:
        _shutdown_processes(processes)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    if not args.no_open:
        thread = threading.Thread(target=_open_urls, args=([dashboard_url, foundation_url],), daemon=True)
        thread.start()

    try:
        while True:
            for name, proc in processes:
                rc = proc.poll()
                if rc is not None:
                    print(f"[operator-surface] {name} exited with code {rc}")
                    _shutdown_processes(processes)
                    return rc
            time.sleep(0.4)
    except KeyboardInterrupt:
        pass

    _shutdown_processes(processes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
