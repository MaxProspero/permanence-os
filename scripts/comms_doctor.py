#!/usr/bin/env python3
"""
Comms stack doctor checks for configuration, automation, and freshness.

Outputs:
- outputs/comms_doctor_<timestamp>.md
- outputs/comms_doctor_latest.md
- memory/tool/comms_doctor_<timestamp>.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

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

WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
FEEDS_PATH = Path(
    os.getenv("PERMANENCE_SOCIAL_RESEARCH_FEEDS_PATH", str(WORKING_DIR / "social_research_feeds.json"))
)
ESCALATIONS_PATH = Path(
    os.getenv(
        "PERMANENCE_COMMS_ESCALATIONS_PATH",
        str(WORKING_DIR / "comms" / "escalations.jsonl"),
    )
)

COMMS_LOOP_LABEL = "com.permanence.comms_loop"
COMMS_DIGEST_LABEL = "com.permanence.comms_digest"
COMMS_DOCTOR_LABEL = "com.permanence.comms_doctor"
COMMS_ESCALATION_DIGEST_LABEL = "com.permanence.comms_escalation_digest"


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


def _staleness_minutes(path: Path | None) -> int | None:
    if path is None or (not path.exists()):
        return None
    delta = _now().timestamp() - path.stat().st_mtime
    if delta < 0:
        return 0
    return int(delta // 60)


def _launchd_state(label: str) -> dict[str, Any]:
    uid = os.getuid()
    target = f"gui/{uid}/{label}"
    try:
        proc = subprocess.run(
            ["launchctl", "print", target],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return {
            "label": label,
            "installed": False,
            "state": "unknown",
            "runs": 0,
            "last_exit_code": None,
        }

    if proc.returncode != 0:
        return {
            "label": label,
            "installed": False,
            "state": "missing",
            "runs": 0,
            "last_exit_code": None,
        }

    text = proc.stdout or ""
    state_match = re.search(r"state = ([^\n]+)", text)
    runs_match = re.search(r"runs = (\d+)", text)
    code_match = re.search(r"last exit code = (\d+)", text)
    return {
        "label": label,
        "installed": True,
        "state": (state_match.group(1).strip() if state_match else "unknown"),
        "runs": int(runs_match.group(1)) if runs_match else 0,
        "last_exit_code": int(code_match.group(1)) if code_match else None,
    }


def _bool_env_present(key: str) -> bool:
    return bool(str(os.getenv(key, "")).strip())


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _live_telegram_check(timeout: int) -> dict[str, Any]:
    token = str(os.getenv("PERMANENCE_TELEGRAM_BOT_TOKEN", "")).strip()
    if not token:
        return {"checked": False, "ok": False, "status_code": None, "error": "missing token"}
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        response = requests.get(url, timeout=max(2, int(timeout)))
    except Exception as exc:  # noqa: BLE001
        return {"checked": True, "ok": False, "status_code": None, "error": str(exc)}
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    ok = response.status_code == 200 and bool(payload.get("ok"))
    return {
        "checked": True,
        "ok": ok,
        "status_code": int(response.status_code),
        "error": "" if ok else str(payload.get("description") or "telegram getMe failed"),
    }


def _live_discord_check(timeout: int) -> dict[str, Any]:
    token = str(os.getenv("PERMANENCE_DISCORD_BOT_TOKEN", "")).strip()
    if not token:
        return {"checked": False, "ok": False, "status_code": None, "error": "missing token"}
    try:
        response = requests.get(
            "https://discord.com/api/v10/users/@me",
            timeout=max(2, int(timeout)),
            headers={"Authorization": f"Bot {token}", "User-Agent": "permanence-os-comms-doctor"},
        )
    except Exception as exc:  # noqa: BLE001
        return {"checked": True, "ok": False, "status_code": None, "error": str(exc)}
    ok = response.status_code == 200
    error = ""
    if not ok:
        try:
            payload = response.json()
            error = str(payload.get("message") or f"discord status {response.status_code}")
        except ValueError:
            error = f"discord status {response.status_code}"
    return {
        "checked": True,
        "ok": ok,
        "status_code": int(response.status_code),
        "error": error,
    }


def _live_token_checks(timeout: int) -> dict[str, Any]:
    return {
        "telegram": _live_telegram_check(timeout=timeout),
        "discord": _live_discord_check(timeout=timeout),
    }


def _run_cli(args: list[str], timeout: int) -> dict[str, Any]:
    argv = [sys.executable, str(BASE_DIR / "cli.py"), *args]
    try:
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR),
            timeout=max(5, int(timeout)),
        )
    except subprocess.TimeoutExpired:
        return {
            "argv": argv,
            "ok": False,
            "returncode": 124,
            "stdout": "",
            "stderr": f"timed out after {max(5, int(timeout))}s",
        }
    return {
        "argv": argv,
        "ok": proc.returncode == 0,
        "returncode": int(proc.returncode),
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def _feed_stats(path: Path) -> dict[str, Any]:
    rows = _read_json(path, [])
    if not isinstance(rows, list):
        rows = []
    discord_rows = [row for row in rows if isinstance(row, dict) and str(row.get("platform") or "").lower() == "discord"]
    enabled_rows = [row for row in discord_rows if row.get("enabled", True) is not False]
    enabled_with_channel = [row for row in enabled_rows if str(row.get("channel_id") or "").strip()]
    return {
        "path": str(path),
        "exists": path.exists(),
        "discord_rows": len(discord_rows),
        "enabled_discord_rows": len(enabled_rows),
        "enabled_with_channel_id": len(enabled_with_channel),
    }


def _escalation_stats(path: Path, lookback_hours: int = 24) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "total": 0, "recent": 0}
    total = 0
    recent = 0
    cutoff = _now().timestamp() - max(1, int(lookback_hours)) * 3600
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        token = line.strip()
        if not token:
            continue
        try:
            row = json.loads(token)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        total += 1
        created_at = str(row.get("created_at") or "").strip()
        try:
            ts = datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            ts = 0
        if ts >= cutoff:
            recent += 1
    return {"path": str(path), "exists": True, "total": total, "recent": recent}


def _component_freshness(prefix: str, max_stale_minutes: int) -> dict[str, Any]:
    path = _latest_json(prefix)
    stale_minutes = _staleness_minutes(path)
    status = "missing"
    if path:
        status = "ok"
        if stale_minutes is not None and stale_minutes > max_stale_minutes:
            status = "stale"
    return {
        "prefix": prefix,
        "path": str(path) if path else "",
        "present": bool(path),
        "stale_minutes": stale_minutes,
        "max_stale_minutes": max_stale_minutes,
        "status": status,
    }


def _build_payload(
    *,
    max_stale_minutes: int,
    digest_max_stale_minutes: int,
    require_digest: bool,
    require_escalation_digest: bool,
    check_live: bool,
    live_timeout: int,
    auto_repair: bool,
    repair_timeout: int,
) -> dict[str, Any]:
    env_checks = {
        "PERMANENCE_DISCORD_BOT_TOKEN": _bool_env_present("PERMANENCE_DISCORD_BOT_TOKEN"),
        "PERMANENCE_TELEGRAM_BOT_TOKEN": _bool_env_present("PERMANENCE_TELEGRAM_BOT_TOKEN"),
        "PERMANENCE_TELEGRAM_CHAT_ID": _bool_env_present("PERMANENCE_TELEGRAM_CHAT_ID"),
    }

    feeds = _feed_stats(FEEDS_PATH)
    escalations = _escalation_stats(ESCALATIONS_PATH)
    launchd = {
        "comms_loop": _launchd_state(COMMS_LOOP_LABEL),
        "comms_digest": _launchd_state(COMMS_DIGEST_LABEL),
        "comms_doctor": _launchd_state(COMMS_DOCTOR_LABEL),
        "comms_escalation_digest": _launchd_state(COMMS_ESCALATION_DIGEST_LABEL),
    }
    live_checks = _live_token_checks(timeout=live_timeout) if check_live else {}
    repair_runs: list[dict[str, Any]] = []

    components = {
        "telegram_control": _component_freshness("telegram_control", max_stale_minutes=max_stale_minutes),
        "discord_telegram_relay": _component_freshness("discord_telegram_relay", max_stale_minutes=max_stale_minutes),
        "glasses_autopilot": _component_freshness("glasses_autopilot", max_stale_minutes=max_stale_minutes),
        "integration_readiness": _component_freshness("integration_readiness", max_stale_minutes=max_stale_minutes),
        "comms_status": _component_freshness("comms_status", max_stale_minutes=max_stale_minutes),
        "comms_digest": _component_freshness("comms_digest", max_stale_minutes=digest_max_stale_minutes),
        "comms_escalation_digest": _component_freshness(
            "comms_escalation_digest", max_stale_minutes=digest_max_stale_minutes
        ),
    }

    warnings: list[str] = []
    actions: list[str] = []

    for key, present in env_checks.items():
        if not present:
            warnings.append(f"Missing required env: {key}")
    if warnings:
        actions.append("Set missing secrets/chat id in .env, then rerun `python cli.py comms-doctor`.")

    if not feeds.get("exists"):
        warnings.append("Discord feeds file is missing.")
        actions.append("Run `python cli.py discord-feed-manager --action add ...` to create Discord feed rows.")
    elif int(feeds.get("enabled_with_channel_id", 0)) == 0:
        warnings.append("No enabled Discord feed rows with channel_id.")
        actions.append("Enable at least one feed with channel id via `python cli.py discord-feed-manager --action enable ...`.")

    loop_state = launchd.get("comms_loop", {})
    if not bool(loop_state.get("installed")):
        warnings.append("Comms loop automation is not installed.")
        actions.append("Run `python cli.py comms-automation --action enable`.")
    elif loop_state.get("last_exit_code") not in {0, None}:
        warnings.append(f"Comms loop last exit code is {loop_state.get('last_exit_code')} (expected 0).")
        actions.append("Inspect `logs/automation/comms_loop*.log` and fix failing step.")

    if require_digest:
        digest_state = launchd.get("comms_digest", {})
        if not bool(digest_state.get("installed")):
            warnings.append("Comms digest automation is required but not installed.")
            actions.append("Run `python cli.py comms-automation --action digest-enable`.")
        elif digest_state.get("last_exit_code") not in {0, None}:
            warnings.append(f"Comms digest last exit code is {digest_state.get('last_exit_code')} (expected 0).")
    if require_escalation_digest:
        escalation_state = launchd.get("comms_escalation_digest", {})
        if not bool(escalation_state.get("installed")):
            warnings.append("Comms escalation digest automation is required but not installed.")
            actions.append("Run `python cli.py comms-automation --action escalation-enable`.")
        elif escalation_state.get("last_exit_code") not in {0, None}:
            warnings.append(
                "Comms escalation digest last exit code is "
                f"{escalation_state.get('last_exit_code')} (expected 0)."
            )

    doctor_state = launchd.get("comms_doctor", {})
    if not bool(doctor_state.get("installed")):
        warnings.append("Comms doctor automation is not installed.")
        actions.append("Run `python cli.py comms-automation --action doctor-enable`.")

    if check_live:
        for system in ("telegram", "discord"):
            row = live_checks.get(system) if isinstance(live_checks.get(system), dict) else {}
            if not row.get("checked"):
                continue
            if not bool(row.get("ok")):
                warnings.append(f"{system} token live check failed: {row.get('error') or 'unknown error'}")
                if system == "telegram":
                    actions.append("Refresh `PERMANENCE_TELEGRAM_BOT_TOKEN` and confirm `PERMANENCE_TELEGRAM_CHAT_ID`.")
                if system == "discord":
                    actions.append("Regenerate `PERMANENCE_DISCORD_BOT_TOKEN` and re-invite bot with channel read permission.")

    escalation_warn_count = max(1, int(os.getenv("PERMANENCE_COMMS_DOCTOR_ESCALATION_WARN_COUNT", "8")))
    if int(escalations.get("recent", 0)) >= escalation_warn_count:
        warnings.append(
            f"High escalation volume in last 24h: {escalations.get('recent')} (threshold {escalation_warn_count})"
        )
        actions.append("Review escalations queue and update Discord keyword filters/priorities.")

    if auto_repair:
        if not bool(loop_state.get("installed")):
            repair_runs.append(_run_cli(["comms-automation", "--action", "enable"], timeout=repair_timeout))
        if require_digest and not bool(launchd.get("comms_digest", {}).get("installed")):
            repair_runs.append(_run_cli(["comms-automation", "--action", "digest-enable"], timeout=repair_timeout))
        if require_escalation_digest and not bool(launchd.get("comms_escalation_digest", {}).get("installed")):
            repair_runs.append(_run_cli(["comms-automation", "--action", "escalation-enable"], timeout=repair_timeout))
        if not bool(doctor_state.get("installed")):
            repair_runs.append(_run_cli(["comms-automation", "--action", "doctor-enable"], timeout=repair_timeout))
        if repair_runs:
            launchd = {
                "comms_loop": _launchd_state(COMMS_LOOP_LABEL),
                "comms_digest": _launchd_state(COMMS_DIGEST_LABEL),
                "comms_doctor": _launchd_state(COMMS_DOCTOR_LABEL),
                "comms_escalation_digest": _launchd_state(COMMS_ESCALATION_DIGEST_LABEL),
            }
            for run in repair_runs:
                if not bool(run.get("ok")):
                    warnings.append(f"auto-repair failed: {' '.join(run.get('argv') or [])}")

    for key, row in components.items():
        if key == "comms_digest" and (not require_digest) and (not row.get("present")):
            continue
        if key == "comms_escalation_digest" and (not require_escalation_digest) and (not row.get("present")):
            continue
        if row.get("status") == "missing":
            warnings.append(f"Component payload missing: {key}")
        elif row.get("status") == "stale":
            warnings.append(
                f"Component payload stale: {key} ({row.get('stale_minutes')}m > {row.get('max_stale_minutes')}m)"
            )

    if any("Component payload" in item for item in warnings):
        actions.append("Run `python cli.py comms-loop` once to refresh payloads.")
    if (not require_digest) and components["comms_digest"].get("status") == "missing":
        actions.append("Optional: enable digest via `python cli.py comms-automation --action digest-enable`.")
    if (not require_escalation_digest) and components["comms_escalation_digest"].get("status") == "missing":
        actions.append("Optional: enable escalation digest via `python cli.py comms-automation --action escalation-enable`.")

    # Keep order stable while deduplicating.
    dedup_actions: list[str] = []
    seen: set[str] = set()
    for item in actions:
        if item in seen:
            continue
        seen.add(item)
        dedup_actions.append(item)

    return {
        "generated_at": _now_iso(),
        "config": {
            "max_stale_minutes": max_stale_minutes,
            "digest_max_stale_minutes": digest_max_stale_minutes,
            "require_digest": require_digest,
            "require_escalation_digest": require_escalation_digest,
            "check_live": check_live,
            "auto_repair": auto_repair,
        },
        "env_checks": env_checks,
        "feeds": feeds,
        "escalations": escalations,
        "launchd": launchd,
        "live_checks": live_checks,
        "auto_repair_runs": repair_runs,
        "components": components,
        "warnings": warnings,
        "recommended_actions": dedup_actions,
    }


def _write_report(payload: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)

    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"comms_doctor_{stamp}.md"
    latest_md = OUTPUT_DIR / "comms_doctor_latest.md"
    json_path = TOOL_DIR / f"comms_doctor_{stamp}.json"

    env_checks = payload.get("env_checks") if isinstance(payload.get("env_checks"), dict) else {}
    feeds = payload.get("feeds") if isinstance(payload.get("feeds"), dict) else {}
    escalations = payload.get("escalations") if isinstance(payload.get("escalations"), dict) else {}
    launchd = payload.get("launchd") if isinstance(payload.get("launchd"), dict) else {}
    live_checks = payload.get("live_checks") if isinstance(payload.get("live_checks"), dict) else {}
    repair_runs = payload.get("auto_repair_runs") if isinstance(payload.get("auto_repair_runs"), list) else []
    components = payload.get("components") if isinstance(payload.get("components"), dict) else {}
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    actions = payload.get("recommended_actions") if isinstance(payload.get("recommended_actions"), list) else []

    lines = [
        "# Comms Doctor",
        "",
        f"Generated (UTC): {payload.get('generated_at', _now_iso())}",
        "",
        "## Env Checks",
    ]
    for key in (
        "PERMANENCE_DISCORD_BOT_TOKEN",
        "PERMANENCE_TELEGRAM_BOT_TOKEN",
        "PERMANENCE_TELEGRAM_CHAT_ID",
    ):
        lines.append(f"- {key}: {'set' if bool(env_checks.get(key)) else 'missing'}")

    lines.extend(
        [
            "",
            "## Discord Feeds",
            f"- Path: {feeds.get('path', '-')}",
            f"- Exists: {bool(feeds.get('exists'))}",
            f"- Discord rows: {feeds.get('discord_rows', 0)}",
            f"- Enabled rows: {feeds.get('enabled_discord_rows', 0)}",
            f"- Enabled with channel_id: {feeds.get('enabled_with_channel_id', 0)}",
            "",
            "## Escalations",
            f"- Path: {escalations.get('path', '-')}",
            f"- Exists: {bool(escalations.get('exists'))}",
            f"- Total entries: {escalations.get('total', 0)}",
            f"- Last 24h: {escalations.get('recent', 0)}",
            "",
            "## Launchd",
        ]
    )
    for name in ("comms_loop", "comms_digest", "comms_doctor", "comms_escalation_digest"):
        row = launchd.get(name) if isinstance(launchd.get(name), dict) else {}
        lines.append(
            f"- {name}: installed={bool(row.get('installed'))}, state={row.get('state')}, "
            f"runs={row.get('runs')}, last_exit={row.get('last_exit_code')}"
        )

    if live_checks:
        lines.extend(["", "## Live Token Checks"])
        for system in ("telegram", "discord"):
            row = live_checks.get(system) if isinstance(live_checks.get(system), dict) else {}
            lines.append(
                f"- {system}: checked={bool(row.get('checked'))}, ok={bool(row.get('ok'))}, "
                f"status_code={row.get('status_code')}, error={row.get('error') or '-'}"
            )

    if repair_runs:
        lines.extend(["", "## Auto Repair"])
        for run in repair_runs[:20]:
            argv = " ".join(str(item) for item in (run.get("argv") or []))
            lines.append(
                f"- ok={bool(run.get('ok'))}, returncode={run.get('returncode')}, argv={argv or '-'}"
            )

    lines.extend(["", "## Component Freshness"])
    for key in (
        "telegram_control",
        "discord_telegram_relay",
        "glasses_autopilot",
        "integration_readiness",
        "comms_status",
        "comms_digest",
        "comms_escalation_digest",
    ):
        row = components.get(key) if isinstance(components.get(key), dict) else {}
        lines.append(
            f"- {key}: status={row.get('status')}, stale_minutes={row.get('stale_minutes')}, path={row.get('path') or '-'}"
        )

    lines.extend(["", "## Warnings"])
    if warnings:
        for item in warnings:
            lines.append(f"- {item}")
    else:
        lines.append("- None")

    lines.extend(["", "## Recommended Actions"])
    if actions:
        for item in actions:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.append("")

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comms health doctor")
    parser.add_argument(
        "--max-stale-minutes",
        type=int,
        default=int(os.getenv("PERMANENCE_COMMS_DOCTOR_MAX_STALE_MINUTES", "45")),
        help="Max allowed stale minutes for core comms payloads",
    )
    parser.add_argument(
        "--digest-max-stale-minutes",
        type=int,
        default=int(os.getenv("PERMANENCE_COMMS_DOCTOR_DIGEST_MAX_STALE_MINUTES", "1500")),
        help="Max allowed stale minutes for comms digest payload",
    )
    parser.add_argument(
        "--require-digest",
        action="store_true",
        default=str(os.getenv("PERMANENCE_COMMS_DOCTOR_REQUIRE_DIGEST", "0")).strip().lower() in {"1", "true", "yes"},
        help="Require digest automation/payload checks to pass",
    )
    parser.add_argument(
        "--require-escalation-digest",
        action="store_true",
        default=str(os.getenv("PERMANENCE_COMMS_DOCTOR_REQUIRE_ESCALATION_DIGEST", "0")).strip().lower()
        in {"1", "true", "yes"},
        help="Require escalation digest automation/payload checks to pass",
    )
    parser.add_argument(
        "--check-live",
        action="store_true",
        default=_is_true(os.getenv("PERMANENCE_COMMS_DOCTOR_CHECK_LIVE", "1")),
        help="Run live token checks against Telegram/Discord APIs",
    )
    parser.add_argument(
        "--live-timeout",
        type=int,
        default=int(os.getenv("PERMANENCE_COMMS_DOCTOR_LIVE_TIMEOUT", "8")),
        help="Timeout seconds for live token checks",
    )
    parser.add_argument("--auto-repair", action="store_true", help="Attempt to auto-enable missing comms automations")
    parser.add_argument(
        "--repair-timeout",
        type=int,
        default=int(os.getenv("PERMANENCE_COMMS_DOCTOR_REPAIR_TIMEOUT", "120")),
        help="Timeout seconds for each repair command",
    )
    parser.add_argument("--allow-warnings", action="store_true", help="Exit 0 even when warnings exist")
    args = parser.parse_args(argv)

    payload = _build_payload(
        max_stale_minutes=max(1, int(args.max_stale_minutes)),
        digest_max_stale_minutes=max(1, int(args.digest_max_stale_minutes)),
        require_digest=bool(args.require_digest),
        require_escalation_digest=bool(args.require_escalation_digest),
        check_live=bool(args.check_live),
        live_timeout=max(2, int(args.live_timeout)),
        auto_repair=bool(args.auto_repair),
        repair_timeout=max(5, int(args.repair_timeout)),
    )
    md_path, json_path = _write_report(payload)

    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    print(f"Comms doctor written: {md_path}")
    print(f"Comms doctor latest: {OUTPUT_DIR / 'comms_doctor_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Warnings: {len(warnings)}")
    if warnings and not args.allow_warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
