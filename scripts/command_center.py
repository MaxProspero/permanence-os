#!/usr/bin/env python3
"""
Start the Permanence OS live command center.

Runs the local dashboard API + web UI from one command and can optionally
generate a fresh Horizon report before boot.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import webbrowser

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _open_browser(url: str, delay_seconds: float = 1.0) -> None:
    time.sleep(delay_seconds)
    webbrowser.open(url)


def _run_horizon(demo: bool) -> int:
    cmd = [sys.executable, os.path.join(BASE_DIR, "horizon_agent.py")]
    if demo:
        cmd.append("--demo")
    print(f"[command-center] Running Horizon Agent: {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=BASE_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Permanence OS live command center.")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard API bind host")
    parser.add_argument("--port", type=int, default=8000, help="Dashboard API bind port")
    parser.add_argument("--no-open", action="store_true", help="Do not auto-open browser")
    parser.add_argument(
        "--run-horizon",
        action="store_true",
        help="Run Horizon Agent before starting dashboard API",
    )
    parser.add_argument(
        "--demo-horizon",
        action="store_true",
        help="When used with --run-horizon, run Horizon Agent in deterministic demo mode",
    )
    args = parser.parse_args()

    if args.demo_horizon and not args.run_horizon:
        parser.error("--demo-horizon requires --run-horizon")

    if args.run_horizon:
        code = _run_horizon(demo=args.demo_horizon)
        if code != 0:
            return code

    url = f"http://{args.host}:{args.port}"
    if not args.no_open:
        thread = threading.Thread(target=_open_browser, args=(url,), daemon=True)
        thread.start()

    env = os.environ.copy()
    env["PERMANENCE_BASE_DIR"] = BASE_DIR
    env["PERMANENCE_DASHBOARD_HOST"] = args.host
    env["PERMANENCE_DASHBOARD_PORT"] = str(args.port)

    cmd = [sys.executable, os.path.join(BASE_DIR, "dashboard_api.py")]
    print(f"[command-center] Starting dashboard on {url}")
    return subprocess.call(cmd, cwd=BASE_DIR, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
