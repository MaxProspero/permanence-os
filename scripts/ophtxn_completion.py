#!/usr/bin/env python3
"""
Score Ophtxn program completion from live telemetry and list blockers to 100%.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env()

OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return payload


def _latest_json(prefix: str, root: Path | None = None) -> Path | None:
    base = root or TOOL_DIR
    if not base.exists():
        return None
    rows = sorted(base.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_payloads(root: Path | None = None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for prefix in (
        "integration_readiness",
        "comms_status",
        "comms_doctor",
        "telegram_control",
        "discord_telegram_relay",
        "ophtxn_brain",
        "self_improvement",
        "governed_learning",
        "terminal_task_queue",
        "x_account_watch",
    ):
        path = _latest_json(prefix, root=root)
        payload = _read_json(path, {}) if path else {}
        out[prefix] = payload if isinstance(payload, dict) else {}
        out[f"{prefix}_path"] = {"path": str(path) if path else ""}
    return out


def _score_payloads(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    next_actions: list[str] = []
    pillars: list[dict[str, Any]] = []

    def check(cond: bool, points: int, ok_detail: str, fail_detail: str, fail_action: str) -> dict[str, Any]:
        if cond:
            return {"status": "PASS", "earned": points, "points": points, "detail": ok_detail}
        blockers.append(fail_detail)
        next_actions.append(fail_action)
        return {"status": "FAIL", "earned": 0, "points": points, "detail": fail_detail}

    integration = payloads.get("integration_readiness", {})
    comms_status = payloads.get("comms_status", {})
    comms_doctor = payloads.get("comms_doctor", {})
    telegram = payloads.get("telegram_control", {})
    relay = payloads.get("discord_telegram_relay", {})
    brain = payloads.get("ophtxn_brain", {})
    improve = payloads.get("self_improvement", {})
    learning = payloads.get("governed_learning", {})
    queue = payloads.get("terminal_task_queue", {})
    x_watch = payloads.get("x_account_watch", {})

    intake_mirror_enabled = _is_true(os.getenv("PERMANENCE_DISCORD_RELAY_INTAKE_MIRROR", "1"))
    shared_intake_path = Path(
        os.getenv(
            "PERMANENCE_TELEGRAM_CONTROL_INTAKE_PATH",
            str(WORKING_DIR.parent / "inbox" / "telegram_share_intake.jsonl"),
        )
    )
    has_shared_intake = shared_intake_path.exists()

    personal_checks = [
        check(
            cond=bool(telegram.get("chat_agent_enabled")),
            points=8,
            ok_detail="Telegram chat-agent enabled.",
            fail_detail="Telegram chat-agent disabled.",
            fail_action="Enable PERMANENCE_TELEGRAM_CONTROL_CHAT_AGENT_ENABLED=1.",
        ),
        check(
            cond=len(telegram.get("target_chat_ids") or []) >= 2,
            points=8,
            ok_detail="Telegram scope includes DM + channel.",
            fail_detail="Telegram scope is not covering both DM and channel.",
            fail_action="Set PERMANENCE_TELEGRAM_CONTROL_TARGET_CHAT_IDS to include both chat IDs.",
        ),
        check(
            cond=_safe_int(brain.get("chunk_count"), 0) >= 150,
            points=7,
            ok_detail=f"Brain vault has {_safe_int(brain.get('chunk_count'), 0)} chunks.",
            fail_detail="Brain vault is under-populated (<150 chunks).",
            fail_action="Run `python cli.py ophtxn-brain --action sync` and expand intake sources.",
        ),
        check(
            cond=not bool(integration.get("blocked")),
            points=7,
            ok_detail="Required integrations are ready.",
            fail_detail="Required integrations are blocked.",
            fail_action="Run `python cli.py integration-readiness` and clear required missing checks.",
        ),
    ]
    pillars.append({"name": "Personal Core", "max_points": 30, "checks": personal_checks})

    comms_checks = [
        check(
            cond=not bool(comms_status.get("warnings")),
            points=8,
            ok_detail="Comms status warnings are clear.",
            fail_detail="Comms status has warnings.",
            fail_action="Run `python cli.py comms-status` and resolve warning entries.",
        ),
        check(
            cond=not bool(comms_doctor.get("warnings")),
            points=6,
            ok_detail="Comms doctor warnings are clear.",
            fail_detail="Comms doctor found warnings.",
            fail_action="Run `python cli.py comms-doctor --check-live --auto-repair --allow-warnings`.",
        ),
        check(
            cond=_safe_int(relay.get("active_feeds"), 0) >= 1,
            points=6,
            ok_detail="Discord relay has active feeds.",
            fail_detail="Discord relay has zero active feeds.",
            fail_action="Add/enable at least one Discord feed via `python cli.py discord-feed-manager --action add ...`.",
        ),
    ]
    pillars.append({"name": "Comms Fabric", "max_points": 20, "checks": comms_checks})

    learning_checks = [
        check(
            cond=bool(improve.get("policy_enabled")),
            points=5,
            ok_detail="Self-improvement policy enabled.",
            fail_detail="Self-improvement policy disabled.",
            fail_action="Enable self-improvement policy and run `python cli.py self-improvement --action status`.",
        ),
        check(
            cond=_safe_int(improve.get("pending_count"), 0) <= 2,
            points=5,
            ok_detail=f"Self-improvement pending proposals healthy ({_safe_int(improve.get('pending_count'), 0)}).",
            fail_detail=f"Self-improvement queue too large ({_safe_int(improve.get('pending_count'), 0)} pending).",
            fail_action="Review pending proposals and decide approve/reject/defer.",
        ),
        check(
            cond=bool(learning.get("policy_enabled")),
            points=10,
            ok_detail="Governed learning policy enabled.",
            fail_detail="Governed learning policy disabled.",
            fail_action="Enable governed learning policy and schedule run cadence.",
        ),
    ]
    pillars.append({"name": "Learning Loop", "max_points": 20, "checks": learning_checks})

    research_checks = [
        check(
            cond=len(x_watch.get("watched_accounts") or []) >= 3,
            points=5,
            ok_detail=f"X research watchlist seeded ({len(x_watch.get('watched_accounts') or [])} accounts).",
            fail_detail="X research watchlist not sufficiently seeded.",
            fail_action="Add at least 3 high-signal X accounts via `python cli.py x-account-watch --action add --handle @...`.",
        ),
        check(
            cond=has_shared_intake,
            points=5,
            ok_detail="Shared intake path exists for unified memory.",
            fail_detail="Shared intake path is missing.",
            fail_action="Run telegram-control poll once to create intake stream.",
        ),
        check(
            cond=intake_mirror_enabled,
            points=5,
            ok_detail="Discord intake mirror enabled.",
            fail_detail="Discord intake mirror disabled.",
            fail_action="Set PERMANENCE_DISCORD_RELAY_INTAKE_MIRROR=1.",
        ),
    ]
    pillars.append({"name": "Research + Memory", "max_points": 15, "checks": research_checks})

    pending_tasks = _safe_int(queue.get("pending_count"), 0)
    queue_healthy = pending_tasks <= 1
    queue_partial = pending_tasks <= 5
    if queue_healthy:
        queue_check = {"status": "PASS", "earned": 8, "points": 8, "detail": "Terminal task queue near-zero backlog."}
    elif queue_partial:
        queue_check = {
            "status": "PARTIAL",
            "earned": 4,
            "points": 8,
            "detail": f"Terminal queue has moderate backlog ({pending_tasks}).",
        }
        blockers.append(f"Terminal queue backlog still open ({pending_tasks} pending).")
        next_actions.append("Close pending terminal tasks until backlog <= 1.")
    else:
        queue_check = {
            "status": "FAIL",
            "earned": 0,
            "points": 8,
            "detail": f"Terminal queue backlog high ({pending_tasks}).",
        }
        blockers.append(f"Terminal queue backlog high ({pending_tasks} pending).")
        next_actions.append("Prioritize terminal queue burn-down this week.")

    launchd = (comms_status.get("launchd") or {}) if isinstance(comms_status.get("launchd"), dict) else {}
    launchd_state = str(launchd.get("state") or "").strip().lower()
    launchd_last_exit = launchd.get("last_exit_code")
    launchd_ok = bool(launchd.get("installed")) and (
        launchd_state in {"running", "xpcproxy"}
        or launchd_last_exit in {None, 0}
    )
    launchd_check = check(
        cond=launchd_ok,
        points=7,
        ok_detail="Comms loop automation installed and running.",
        fail_detail="Comms loop automation is not running.",
        fail_action="Re-enable comms automation via `python cli.py comms-automation --action enable`.",
    )
    execution_checks = [queue_check, launchd_check]
    pillars.append({"name": "Execution Ops", "max_points": 15, "checks": execution_checks})

    total_points = sum(_safe_int(pillar.get("max_points"), 0) for pillar in pillars)
    earned_points = sum(_safe_int(check_row.get("earned"), 0) for pillar in pillars for check_row in pillar["checks"])
    completion_pct = int(round((earned_points / max(1, total_points)) * 100))

    for pillar in pillars:
        pillar_earned = sum(_safe_int(row.get("earned"), 0) for row in pillar["checks"])
        pillar["earned_points"] = pillar_earned
        pillar["completion_pct"] = int(round((pillar_earned / max(1, _safe_int(pillar.get("max_points"), 0))) * 100))

    unique_actions: list[str] = []
    seen_actions: set[str] = set()
    for action in next_actions:
        key = action.strip()
        if not key or key in seen_actions:
            continue
        seen_actions.add(key)
        unique_actions.append(key)

    return {
        "generated_at": _now_iso(),
        "completion_pct": completion_pct,
        "earned_points": earned_points,
        "total_points": total_points,
        "pillars": pillars,
        "blockers": blockers,
        "next_actions": unique_actions[:12],
        "live_snapshot": {
            "integration_blocked": bool(integration.get("blocked")),
            "comms_warnings": len(comms_status.get("warnings") or []),
            "doctor_warnings": len(comms_doctor.get("warnings") or []),
            "telegram_updates": _safe_int(telegram.get("updates_count"), 0),
            "telegram_ingested": _safe_int(telegram.get("ingested_count"), 0),
            "discord_active_feeds": _safe_int(relay.get("active_feeds"), 0),
            "brain_chunks": _safe_int(brain.get("chunk_count"), 0),
            "self_improvement_pending": _safe_int(improve.get("pending_count"), 0),
            "governed_learning_enabled": bool(learning.get("policy_enabled")),
            "terminal_pending": pending_tasks,
            "x_watch_count": len(x_watch.get("watched_accounts") or []),
        },
        "sources": {
            key: value.get("path", "")
            for key, value in payloads.items()
            if key.endswith("_path") and isinstance(value, dict)
        },
    }


def _write_report(payload: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"ophtxn_completion_{stamp}.md"
    latest_md = OUTPUT_DIR / "ophtxn_completion_latest.md"
    json_path = TOOL_DIR / f"ophtxn_completion_{stamp}.json"

    lines = [
        "# Ophtxn Completion",
        "",
        f"Generated (UTC): {payload.get('generated_at')}",
        "",
        "## Summary",
        f"- Completion: {payload.get('completion_pct')}%",
        f"- Score: {payload.get('earned_points')}/{payload.get('total_points')}",
        "",
        "## Pillars",
    ]
    pillars = payload.get("pillars") if isinstance(payload.get("pillars"), list) else []
    for pillar in pillars:
        if not isinstance(pillar, dict):
            continue
        lines.append(
            f"- {pillar.get('name')}: {pillar.get('earned_points')}/{pillar.get('max_points')} "
            f"({pillar.get('completion_pct')}%)"
        )
        checks = pillar.get("checks") if isinstance(pillar.get("checks"), list) else []
        for row in checks[:20]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"  - {row.get('status')} [{row.get('earned')}/{row.get('points')}] {row.get('detail')}"
            )
    lines.append("")

    blockers = payload.get("blockers") if isinstance(payload.get("blockers"), list) else []
    lines.append("## Blockers")
    if blockers:
        for row in blockers[:25]:
            lines.append(f"- {row}")
    else:
        lines.append("- None")
    lines.append("")

    actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    lines.append("## Next Actions")
    if actions:
        for idx, row in enumerate(actions[:12], start=1):
            lines.append(f"{idx}. {row}")
    else:
        lines.append("1. Continue monitoring; no immediate blockers.")
    lines.append("")

    snapshot = payload.get("live_snapshot") if isinstance(payload.get("live_snapshot"), dict) else {}
    lines.append("## Live Snapshot")
    for key in (
        "integration_blocked",
        "comms_warnings",
        "doctor_warnings",
        "telegram_updates",
        "telegram_ingested",
        "discord_active_feeds",
        "brain_chunks",
        "self_improvement_pending",
        "governed_learning_enabled",
        "terminal_pending",
        "x_watch_count",
    ):
        lines.append(f"- {key}: {snapshot.get(key)}")
    lines.append("")

    report = "\n".join(lines).rstrip() + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    payload = dict(payload)
    payload["latest_markdown"] = str(latest_md)
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score Ophtxn completion and list blockers.")
    parser.add_argument("--target", type=int, default=100, help="Target completion percentage")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when completion < target")
    args = parser.parse_args(argv)

    payloads = _load_payloads()
    scored = _score_payloads(payloads)
    md_path, json_path = _write_report(scored)

    completion = _safe_int(scored.get("completion_pct"), 0)
    target = max(1, min(100, _safe_int(args.target, 100)))
    print(f"Ophtxn completion written: {md_path}")
    print(f"Ophtxn completion latest: {OUTPUT_DIR / 'ophtxn_completion_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Completion: {completion}%")
    print(f"Score: {scored.get('earned_points')}/{scored.get('total_points')}")
    print(f"Blockers: {len(scored.get('blockers') or [])}")
    if args.strict and completion < target:
        print(f"Status: BELOW_TARGET ({completion}% < {target}%)")
        return 1
    print("Status: ON_TRACK" if completion >= target else f"Status: IN_PROGRESS ({completion}% < {target}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
