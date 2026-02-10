#!/usr/bin/env python3
"""
Background reliability watcher.

Runs periodic checks over a fixed-duration window (default 7 days),
notifies only on new failures and final completion, then self-stops.
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from core.storage import storage  # noqa: E402


RUN_FILE_RE = re.compile(r"run_(\d{8}-\d{6})\.log$")
STATUS_RE = re.compile(
    r"Briefing Status:\s*(\d+)\s*\|\s*Digest Status:\s*(\d+)\s*\|\s*NotebookLM Status:\s*(\d+)"
)
WATCH_LABEL = "com.permanence.reliability-watch"
WATCH_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{WATCH_LABEL}.plist"


@dataclass
class RunRecord:
    run_id: str
    path: Path
    started_local: datetime
    briefing_status: int | None
    digest_status: int | None
    notebook_status: int | None

    @property
    def success(self) -> bool:
        return self.briefing_status == 0 and self.digest_status == 0


def _notify(title: str, message: str, log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a") as f:
        f.write(f"{datetime.now().isoformat()} {title}: {message}\n")
    # macOS local notification (best effort)
    if sys.platform == "darwin":
        safe_title = title.replace('"', "'")
        safe_msg = message.replace('"', "'")
        subprocess.run(
            ["osascript", "-e", f'display notification "{safe_msg}" with title "{safe_title}"'],
            check=False,
            capture_output=True,
            text=True,
        )


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _parse_run(path: Path) -> RunRecord | None:
    m = RUN_FILE_RE.search(path.name)
    if not m:
        return None
    try:
        started_local = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    text = path.read_text(errors="ignore")
    status_match = STATUS_RE.search(text)
    if status_match:
        b = int(status_match.group(1))
        d = int(status_match.group(2))
        n = int(status_match.group(3))
    else:
        b = d = n = None
    return RunRecord(
        run_id=path.name,
        path=path,
        started_local=started_local,
        briefing_status=b,
        digest_status=d,
        notebook_status=n,
    )


def _collect_runs(log_dir: Path, start: datetime, end: datetime) -> list[RunRecord]:
    runs: list[RunRecord] = []
    if not log_dir.exists():
        return runs
    for path in sorted(log_dir.glob("run_*.log")):
        run = _parse_run(path)
        if not run:
            continue
        if start <= run.started_local <= end:
            runs.append(run)
    return runs


def _expected_slots(start: datetime, now: datetime, slots: list[int], tolerance_minutes: int) -> list[datetime]:
    effective_end = now
    slot_times: list[datetime] = []
    cur_date = start.date()
    end_date = effective_end.date()
    while cur_date <= end_date:
        for hour in slots:
            slot_dt = datetime(cur_date.year, cur_date.month, cur_date.day, hour, 0, 0)
            # only evaluate slots that are fully due (slot + tolerance has passed)
            if slot_dt < start:
                continue
            if slot_dt + timedelta(minutes=tolerance_minutes) <= effective_end:
                slot_times.append(slot_dt)
        cur_date += timedelta(days=1)
    return slot_times


def _evaluate_window(
    runs: list[RunRecord],
    start: datetime,
    now: datetime,
    slots: list[int],
    tolerance_minutes: int,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    tol = tolerance_minutes * 60
    expected = _expected_slots(start, now, slots, tolerance_minutes)

    failures: list[dict[str, str]] = []
    passed = 0
    missing = 0
    failed = 0
    for slot in expected:
        candidates = [r for r in runs if abs((r.started_local - slot).total_seconds()) <= tol]
        if not candidates:
            missing += 1
            failures.append(
                {
                    "key": f"missing:{slot.isoformat()}",
                    "type": "missing_slot",
                    "detail": f"Missing run near slot {slot.strftime('%Y-%m-%d %H:%M')}",
                }
            )
            continue
        chosen = min(candidates, key=lambda r: abs((r.started_local - slot).total_seconds()))
        if chosen.success:
            passed += 1
            continue
        failed += 1
        failures.append(
            {
                "key": f"failed:{chosen.run_id}",
                "type": "failed_run",
                "detail": (
                    f"Run {chosen.run_id} failed "
                    f"(briefing={chosen.briefing_status}, digest={chosen.digest_status}, notebook={chosen.notebook_status})"
                ),
            }
        )
    summary = {
        "expected_slots": len(expected),
        "passed": passed,
        "missing": missing,
        "failed": failed,
        "ok": (missing == 0 and failed == 0),
    }
    return summary, failures


def _stop_launch_agent(plist_path: Path | None = None) -> None:
    if sys.platform != "darwin":
        return
    target_plist = plist_path or WATCH_PLIST
    if not target_plist.exists():
        return
    subprocess.run(["launchctl", "unload", str(target_plist)], check=False, capture_output=True, text=True)


def _install_launch_agent(
    plist_path: Path,
    state_file: str,
    log_dir: Path,
    alert_log: str,
    check_interval_minutes: int,
) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("LaunchAgent install is supported on macOS only.")
    if check_interval_minutes < 5:
        raise RuntimeError("check interval must be >= 5 minutes.")

    plist_path.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    out_log = log_dir / "reliability_watch.log"
    err_log = log_dir / "reliability_watch.error.log"

    program_args = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--check",
        "--state-file",
        state_file,
        "--log-dir",
        str(log_dir),
        "--alert-log",
        alert_log,
        "--plist-path",
        str(plist_path),
    ]

    payload = {
        "Label": WATCH_LABEL,
        "ProgramArguments": program_args,
        "WorkingDirectory": BASE_DIR,
        "StartInterval": int(check_interval_minutes * 60),
        "StandardOutPath": str(out_log),
        "StandardErrorPath": str(err_log),
        "RunAtLoad": True,
    }

    with plist_path.open("wb") as f:
        plistlib.dump(payload, f)

    subprocess.run(["launchctl", "unload", str(plist_path)], check=False, capture_output=True, text=True)
    proc = subprocess.run(["launchctl", "load", str(plist_path)], check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "launchctl load failed").strip()
        raise RuntimeError(msg)


def _uninstall_launch_agent(plist_path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["launchctl", "unload", str(plist_path)], check=False, capture_output=True, text=True)
    plist_path.unlink(missing_ok=True)


def cmd_start(args: argparse.Namespace) -> int:
    state_path = Path(os.path.expanduser(args.state_file))
    state = _load_state(state_path)
    if state and not args.force and not state.get("completed", False):
        print("Reliability watch already active. Use --force to restart.")
        return 1

    now = datetime.now()
    end = now + timedelta(days=args.days)
    data = {
        "started_at_local": now.isoformat(),
        "ends_at_local": end.isoformat(),
        "days": args.days,
        "slots": args.slots,
        "tolerance_minutes": args.tolerance_minutes,
        "completed": False,
        "stopped": False,
        "notified_keys": [],
        "failures": [],
        "last_summary": {},
        "last_check_local": None,
    }
    _save_state(state_path, data)
    print(f"Reliability watch started: {now.isoformat()} -> {end.isoformat()}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state_path = Path(os.path.expanduser(args.state_file))
    state = _load_state(state_path)
    if not state:
        print("Reliability watch not initialized.")
        return 0
    print(f"started_at_local: {state.get('started_at_local')}")
    print(f"ends_at_local: {state.get('ends_at_local')}")
    print(f"completed: {state.get('completed', False)}")
    print(f"stopped: {state.get('stopped', False)}")
    print(f"last_check_local: {state.get('last_check_local')}")
    print(f"last_summary: {state.get('last_summary')}")
    print(f"failures_logged: {len(state.get('failures', []))}")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    state_path = Path(os.path.expanduser(args.state_file))
    state = _load_state(state_path)
    if not state:
        _stop_launch_agent(Path(os.path.expanduser(args.plist_path)))
        print("Reliability watch not initialized; background agent stopped if present.")
        return 0
    state["stopped"] = True
    state["completed"] = True
    state["last_check_local"] = datetime.now().isoformat()
    _save_state(state_path, state)
    _stop_launch_agent(Path(os.path.expanduser(args.plist_path)))
    print("Reliability watch stopped.")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    state_path = Path(os.path.expanduser(args.state_file))
    alert_log = Path(os.path.expanduser(args.alert_log))
    log_dir = Path(os.path.expanduser(args.log_dir))
    state = _load_state(state_path)
    if not state:
        print("Reliability watch not initialized.")
        return 1
    if state.get("completed") or state.get("stopped"):
        print("Reliability watch already completed/stopped.")
        return 0

    now = datetime.now()
    start = datetime.fromisoformat(state["started_at_local"])
    end = datetime.fromisoformat(state["ends_at_local"])
    window_end = min(now, end)
    slots = [int(x) for x in state.get("slots", [7, 12, 19])]
    tolerance = int(state.get("tolerance_minutes", 90))

    runs = _collect_runs(log_dir, start, window_end)
    summary, failures = _evaluate_window(runs, start, window_end, slots, tolerance)

    notified = set(state.get("notified_keys", []))
    for failure in failures:
        if failure["key"] in notified:
            continue
        _notify("Permanence Reliability Failure", failure["detail"], alert_log)
        notified.add(failure["key"])
        state.setdefault("failures", []).append(
            {
                "key": failure["key"],
                "type": failure["type"],
                "detail": failure["detail"],
                "detected_at_local": now.isoformat(),
            }
        )

    state["notified_keys"] = sorted(notified)
    state["last_summary"] = summary
    state["last_check_local"] = now.isoformat()

    if now >= end:
        state["completed"] = True
        if summary["ok"] and not state.get("failures"):
            _notify("Permanence Reliability Watch Complete", "7-day watch passed with no failures.", alert_log)
            state["result"] = "PASS"
        else:
            _notify(
                "Permanence Reliability Watch Complete",
                f"Completed with failures={summary['failed']} missing={summary['missing']}.",
                alert_log,
            )
            state["result"] = "FAIL"
        _stop_launch_agent(Path(os.path.expanduser(args.plist_path)))

    _save_state(state_path, state)
    print(
        f"Reliability watch check: expected={summary['expected_slots']} "
        f"passed={summary['passed']} missing={summary['missing']} failed={summary['failed']}"
    )
    return 0


def cmd_install_agent(args: argparse.Namespace) -> int:
    try:
        plist_path = Path(os.path.expanduser(args.plist_path))
        log_dir = Path(os.path.expanduser(args.log_dir))
        _install_launch_agent(
            plist_path=plist_path,
            state_file=str(Path(os.path.expanduser(args.state_file))),
            log_dir=log_dir,
            alert_log=str(Path(os.path.expanduser(args.alert_log))),
            check_interval_minutes=args.check_interval_minutes,
        )
    except Exception as exc:
        print(f"Failed to install reliability watch agent: {exc}")
        return 1
    print(f"Reliability watch agent installed: {plist_path}")
    return 0


def cmd_uninstall_agent(args: argparse.Namespace) -> int:
    plist_path = Path(os.path.expanduser(args.plist_path))
    _uninstall_launch_agent(plist_path)
    print(f"Reliability watch agent removed: {plist_path}")
    return 0


def cmd_arm(args: argparse.Namespace) -> int:
    start_rc = cmd_start(args)
    if start_rc != 0:
        return start_rc
    install_rc = cmd_install_agent(args)
    if install_rc != 0:
        return install_rc
    if args.immediate_check:
        return cmd_check(args)
    return 0


def cmd_disarm(args: argparse.Namespace) -> int:
    state_path = Path(os.path.expanduser(args.state_file))
    if state_path.exists():
        cmd_stop(args)
    return cmd_uninstall_agent(args)


def parse_slots(raw: str) -> list[int]:
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Background reliability watch controller.")
    parser.add_argument("--arm", action="store_true", help="Start watch and install background agent")
    parser.add_argument("--disarm", action="store_true", help="Stop watch and remove background agent")
    parser.add_argument("--start", action="store_true", help="Start/reset watch window")
    parser.add_argument("--check", action="store_true", help="Run one background check")
    parser.add_argument("--status", action="store_true", help="Show watch status")
    parser.add_argument("--stop", action="store_true", help="Stop watch and unload agent")
    parser.add_argument("--install-agent", action="store_true", help="Install background launch agent")
    parser.add_argument("--uninstall-agent", action="store_true", help="Uninstall background launch agent")
    parser.add_argument("--force", action="store_true", help="Force restart when --start")
    parser.add_argument("--days", type=int, default=7, help="Watch duration in days")
    parser.add_argument("--slots", default="7,12,19", help="Comma-separated schedule slots")
    parser.add_argument("--tolerance-minutes", type=int, default=90, help="Slot matching tolerance")
    parser.add_argument(
        "--check-interval-minutes",
        type=int,
        default=30,
        help="How often background check runs",
    )
    parser.add_argument(
        "--plist-path",
        default=str(WATCH_PLIST),
        help="LaunchAgent plist path (macOS)",
    )
    parser.add_argument(
        "--no-immediate-check",
        action="store_true",
        help="Do not run a check immediately after --arm",
    )
    parser.add_argument(
        "--state-file",
        default=str(storage.paths.logs / "reliability_watch_state.json"),
        help="State file path",
    )
    parser.add_argument(
        "--log-dir",
        default=str(Path(BASE_DIR) / "logs" / "automation"),
        help="Automation run log directory",
    )
    parser.add_argument(
        "--alert-log",
        default=str(storage.paths.logs / "reliability_watch_alerts.log"),
        help="Alert log path",
    )
    args = parser.parse_args()
    args.slots = parse_slots(args.slots)
    args.immediate_check = not args.no_immediate_check

    mode_count = sum(
        [
            args.arm,
            args.disarm,
            args.start,
            args.check,
            args.status,
            args.stop,
            args.install_agent,
            args.uninstall_agent,
        ]
    )
    if mode_count != 1:
        print(
            "Choose exactly one mode: --arm | --disarm | --start | --check | --status | --stop | "
            "--install-agent | --uninstall-agent"
        )
        return 1

    if args.arm:
        return cmd_arm(args)
    if args.disarm:
        return cmd_disarm(args)
    if args.start:
        return cmd_start(args)
    if args.check:
        return cmd_check(args)
    if args.status:
        return cmd_status(args)
    if args.install_agent:
        return cmd_install_agent(args)
    if args.uninstall_agent:
        return cmd_uninstall_agent(args)
    return cmd_stop(args)


if __name__ == "__main__":
    raise SystemExit(main())
