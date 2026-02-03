#!/usr/bin/env python3
"""
Unified CLI for Permanence OS.
Commands: run, add-source, status, clean, test
"""

import argparse
import os
import subprocess
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))


def _run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def cmd_run(args: argparse.Namespace) -> int:
    cmd = [sys.executable, os.path.join(BASE_DIR, "run_task.py"), args.goal]
    if args.sources:
        cmd += ["--sources", args.sources]
    if args.draft:
        cmd += ["--draft", args.draft]
    return _run(cmd)


def cmd_add_source(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        os.path.join(BASE_DIR, "scripts", "new_sources.py"),
        args.source,
        str(args.confidence),
    ]
    if args.notes:
        cmd.append(args.notes)
    return _run(cmd)


def cmd_status(_args: argparse.Namespace) -> int:
    return _run([sys.executable, os.path.join(BASE_DIR, "scripts", "status.py")])


def cmd_clean(args: argparse.Namespace) -> int:
    cmd = [sys.executable, os.path.join(BASE_DIR, "scripts", "clean_artifacts.py")]
    if args.logs:
        cmd.append("--logs")
    if args.episodic:
        cmd.append("--episodic")
    if args.outputs:
        cmd.append("--outputs")
    if args.all or not (args.logs or args.episodic or args.outputs):
        cmd.append("--all")
    return _run(cmd)


def cmd_test(_args: argparse.Namespace) -> int:
    tests = [
        os.path.join(BASE_DIR, "tests", "test_polemarch.py"),
        os.path.join(BASE_DIR, "tests", "test_agents.py"),
        os.path.join(BASE_DIR, "tests", "test_compliance_gate.py"),
    ]
    exit_code = 0
    for t in tests:
        code = _run([sys.executable, t])
        if code != 0:
            exit_code = code
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Permanence OS CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run governed task workflow")
    run_p.add_argument("goal", help="Task goal")
    run_p.add_argument("--sources", help="Override sources.json path")
    run_p.add_argument("--draft", help="Override draft.md path")
    run_p.set_defaults(func=cmd_run)

    add_p = sub.add_parser("add-source", help="Append a source provenance entry")
    add_p.add_argument("source", help="Source identifier or URL")
    add_p.add_argument("confidence", type=float, help="Confidence (0-1)")
    add_p.add_argument("notes", nargs="?", default="", help="Optional notes")
    add_p.set_defaults(func=cmd_add_source)

    status_p = sub.add_parser("status", help="Show system status")
    status_p.set_defaults(func=cmd_status)

    clean_p = sub.add_parser("clean", help="Clean artifacts")
    clean_p.add_argument("--logs", action="store_true")
    clean_p.add_argument("--episodic", action="store_true")
    clean_p.add_argument("--outputs", action="store_true")
    clean_p.add_argument("--all", action="store_true")
    clean_p.set_defaults(func=cmd_clean)

    test_p = sub.add_parser("test", help="Run test suite")
    test_p.set_defaults(func=cmd_test)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
