#!/usr/bin/env python3
"""
Communication stack status rollup.

Summarizes latest Telegram control, Discord relay, glasses autopilot, and
launchd comms-loop runtime state into one markdown + JSON report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
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
LOG_DIR = Path(os.getenv("PERMANENCE_LOG_DIR", str(BASE_DIR / "logs")))
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
ESCALATIONS_PATH = Path(
    os.getenv("PERMANENCE_COMMS_ESCALATIONS_PATH", str(WORKING_DIR / "comms" / "escalations.jsonl"))
)
TRANSCRIPTION_QUEUE_PATH = Path(
    os.getenv("PERMANENCE_TELEGRAM_TRANSCRIPTION_QUEUE_PATH", str(WORKING_DIR / "transcription_queue.json"))
)
OPENCLAW_CLI = str(os.getenv("OPENCLAW_CLI", "openclaw")).strip() or "openclaw"


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


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        token = line.strip()
        if not token:
            continue
        try:
            payload = json.loads(token)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _latest_json(prefix: str, root: Path | None = None) -> Path | None:
    base = root or TOOL_DIR
    if not base.exists():
        return None
    rows = sorted(base.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _latest_log(prefix: str, root: Path | None = None) -> Path | None:
    base = root or (LOG_DIR / "automation")
    if not base.exists():
        return None
    rows = sorted(base.glob(f"{prefix}_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return rows[0] if rows else None


def _launchd_state(label: str = "com.permanence.comms_loop") -> dict[str, Any]:
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
        return {"installed": False, "state": "unknown", "runs": 0, "last_exit_code": None}

    if proc.returncode != 0:
        return {"installed": False, "state": "missing", "runs": 0, "last_exit_code": None}

    text = proc.stdout or ""
    state_match = re.search(r"state = ([^\n]+)", text)
    runs_match = re.search(r"runs = (\d+)", text)
    code_match = re.search(r"last exit code = (\d+)", text)
    interval_match = re.search(r"run interval = (\d+) seconds", text)
    return {
        "installed": True,
        "state": (state_match.group(1).strip() if state_match else "unknown"),
        "runs": int(runs_match.group(1)) if runs_match else 0,
        "last_exit_code": int(code_match.group(1)) if code_match else None,
        "run_interval_seconds": int(interval_match.group(1)) if interval_match else None,
    }


def _component_status(prefix: str, keys: list[str], root: Path | None = None) -> dict[str, Any]:
    latest = _latest_json(prefix, root=root)
    payload = _read_json(latest, {}) if latest else {}
    if not isinstance(payload, dict):
        payload = {}
    out = {
        "present": bool(latest),
        "path": str(latest) if latest else "",
        "generated_at": str(payload.get("generated_at") or ""),
        "stale_minutes": _staleness_minutes(latest),
    }
    for key in keys:
        out[key] = payload.get(key)
    return out


def _staleness_minutes(path: Path | None) -> int | None:
    if path is None or (not path.exists()):
        return None
    delta = _now().timestamp() - path.stat().st_mtime
    if delta < 0:
        return 0
    return int(delta // 60)


def _escalation_stats(path: Path, lookback_hours: int) -> dict[str, Any]:
    rows = _read_jsonl(path)
    cutoff = _now().timestamp() - max(1, int(lookback_hours)) * 3600
    recent = 0
    priorities: dict[str, int] = {}
    for row in rows:
        created_at = str(row.get("created_at") or "").strip()
        ts = 0.0
        if created_at:
            try:
                ts = datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                ts = 0.0
        if ts >= cutoff:
            recent += 1
            priority = str(row.get("priority") or "normal").strip().lower()
            priorities[priority] = priorities.get(priority, 0) + 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "total": len(rows),
        "recent": recent,
        "lookback_hours": max(1, int(lookback_hours)),
        "recent_by_priority": dict(sorted(priorities.items(), key=lambda item: (-item[1], item[0]))),
    }


def _transcription_queue_stats(path: Path) -> dict[str, Any]:
    rows = _read_json(path, [])
    if not isinstance(rows, list):
        rows = []
    pending = 0
    done = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "queued").strip().lower()
        if status in {"done", "complete", "completed"}:
            done += 1
        else:
            pending += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "total": len(rows),
        "pending": pending,
        "done": done,
    }


def _openclaw_subprocess_env() -> dict[str, str]:
    keys = (
        "HOME",
        "PATH",
        "USER",
        "LOGNAME",
        "SHELL",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TMPDIR",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "OPENCLAW_HOME",
        "OPENCLAW_CONFIG",
        "OPENCLAW_CLI",
    )
    env: dict[str, str] = {}
    for key in keys:
        value = os.getenv(key)
        if value:
            env[key] = value
    env.setdefault("PATH", os.getenv("PATH", os.defpath))
    env.setdefault("HOME", os.path.expanduser("~"))
    return env


def _openclaw_channels_probe(*, timeout_seconds: int = 15) -> dict[str, Any]:
    base = {
        "invoked": False,
        "cli": OPENCLAW_CLI,
        "exit_code": None,
        "gateway_reachable": False,
        "telegram": {
            "found": False,
            "enabled": False,
            "configured": False,
            "running": False,
            "works": False,
            "detail": "",
        },
        "discord": {
            "found": False,
            "enabled": False,
            "configured": False,
            "running": False,
            "works": False,
            "detail": "",
        },
        "imessage": {
            "found": False,
            "enabled": False,
            "configured": False,
            "running": False,
            "works": False,
            "detail": "",
        },
        "error": "",
    }
    try:
        proc = subprocess.run(
            [OPENCLAW_CLI, "channels", "status", "--probe"],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(2, int(timeout_seconds)),
            env=_openclaw_subprocess_env(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        base["error"] = str(exc)
        return base

    combined = "\n".join([proc.stdout or "", proc.stderr or ""]).strip()
    base["invoked"] = True
    base["exit_code"] = proc.returncode
    base["gateway_reachable"] = "gateway reachable" in combined.lower()

    def _line_for(channel_label: str) -> str:
        token = f"- {channel_label.lower()} "
        for raw_line in combined.splitlines():
            line = raw_line.strip()
            if line.lower().startswith(token):
                return line
        return ""

    def _parse_channel(label: str) -> dict[str, Any]:
        line = _line_for(label)
        if not line:
            return {
                "found": False,
                "enabled": False,
                "configured": False,
                "running": False,
                "works": False,
                "detail": "",
            }
        detail = line.split(":", 1)[1].strip() if ":" in line else line
        lower = detail.lower()
        return {
            "found": True,
            "enabled": "enabled" in lower,
            "configured": "configured" in lower,
            "running": "running" in lower,
            "works": "works" in lower,
            "detail": detail,
        }

    base["telegram"] = _parse_channel("Telegram")
    base["discord"] = _parse_channel("Discord")
    base["imessage"] = _parse_channel("iMessage")
    return base


def _build_payload(
    *,
    comms_log_stale_minutes: int,
    component_stale_minutes: int,
    escalation_digest_stale_minutes: int,
    escalation_hours: int,
    escalation_warn_count: int,
    voice_queue_warn_count: int,
    require_escalation_digest: bool,
    check_openclaw_channels: bool,
    require_openclaw_imessage: bool = False,
) -> dict[str, Any]:
    relay = _component_status(
        "discord_telegram_relay",
        keys=["active_feeds", "new_messages", "telegram_messages_sent", "warnings"],
    )
    telegram = _component_status(
        "telegram_control",
        keys=["updates_count", "ingested_count", "ignored_count", "warnings"],
    )
    glasses = _component_status(
        "glasses_autopilot",
        keys=["candidate_count", "imported_count", "skipped_count", "warnings"],
    )
    readiness = _component_status(
        "integration_readiness",
        keys=["status", "warnings", "recommended_actions"],
    )
    escalation_digest = _component_status(
        "comms_escalation_digest",
        keys=["summary", "telegram_sent", "discord_sent", "warnings"],
    )
    openclaw_channels = _openclaw_channels_probe() if check_openclaw_channels else {
        "invoked": False,
        "cli": OPENCLAW_CLI,
        "exit_code": None,
        "gateway_reachable": False,
        "telegram": {"found": False, "enabled": False, "configured": False, "running": False, "works": False, "detail": ""},
        "discord": {"found": False, "enabled": False, "configured": False, "running": False, "works": False, "detail": ""},
        "imessage": {"found": False, "enabled": False, "configured": False, "running": False, "works": False, "detail": ""},
        "error": "probe skipped by config",
    }

    comms_log = _latest_log("comms_loop")
    launchd = _launchd_state()
    escalations = _escalation_stats(ESCALATIONS_PATH, lookback_hours=max(1, int(escalation_hours)))
    transcription_queue = _transcription_queue_stats(TRANSCRIPTION_QUEUE_PATH)

    warnings: list[str] = []
    if not launchd.get("installed"):
        warnings.append("comms loop automation is not installed in launchd.")
    if (launchd.get("last_exit_code") not in {0, None}) and launchd.get("installed"):
        warnings.append(f"launchd last exit code is {launchd.get('last_exit_code')} (expected 0).")
    stale_minutes = _staleness_minutes(comms_log)
    if stale_minutes is not None and stale_minutes > max(1, int(comms_log_stale_minutes)):
        warnings.append(f"latest comms loop log is stale ({stale_minutes} minutes old).")

    for key, row, max_stale in (
        ("discord relay", relay, max(1, int(component_stale_minutes))),
        ("telegram control", telegram, max(1, int(component_stale_minutes))),
        ("glasses autopilot", glasses, max(1, int(component_stale_minutes))),
        ("integration readiness", readiness, max(1, int(component_stale_minutes))),
        ("escalation digest", escalation_digest, max(1, int(escalation_digest_stale_minutes))),
    ):
        stale = row.get("stale_minutes")
        if row.get("present") and isinstance(stale, int) and stale > max_stale:
            warnings.append(f"{key} payload is stale ({stale}m > {max_stale}m).")
    if require_escalation_digest and not escalation_digest.get("present"):
        warnings.append("escalation digest payload missing while required.")
    if relay.get("present") and isinstance(relay.get("warnings"), list) and relay.get("warnings"):
        warnings.append("discord relay reported warnings in latest run.")
    if escalation_digest.get("present") and isinstance(escalation_digest.get("warnings"), list) and escalation_digest.get(
        "warnings"
    ):
        warnings.append("escalation digest reported warnings in latest run.")
    if check_openclaw_channels:
        if (not openclaw_channels.get("invoked")) or openclaw_channels.get("error"):
            warnings.append(
                f"openclaw channel probe unavailable ({openclaw_channels.get('error') or 'command failed'})."
            )
        else:
            for name in ("telegram", "discord"):
                row = openclaw_channels.get(name) if isinstance(openclaw_channels.get(name), dict) else {}
                if not row.get("found"):
                    warnings.append(f"openclaw {name} channel is not configured.")
                    continue
                if not row.get("works"):
                    warnings.append(f"openclaw {name} channel not healthy: {row.get('detail') or 'unknown state'}.")
            imessage_row = (
                openclaw_channels.get("imessage") if isinstance(openclaw_channels.get("imessage"), dict) else {}
            )
            if bool(require_openclaw_imessage):
                if not imessage_row.get("found"):
                    warnings.append("openclaw imessage channel is not configured.")
                elif not imessage_row.get("works"):
                    warnings.append(
                        f"openclaw imessage channel not healthy: {imessage_row.get('detail') or 'unknown state'}."
                    )
            else:
                # Optional iMessage mode: only warn when iMessage is configured and unhealthy.
                if bool(imessage_row.get("configured")) and (not bool(imessage_row.get("works"))):
                    warnings.append(
                        f"openclaw imessage channel not healthy: {imessage_row.get('detail') or 'unknown state'}."
                    )

    if int(escalations.get("recent", 0)) >= max(1, int(escalation_warn_count)):
        warnings.append(
            f"high escalation volume in last {int(escalations.get('lookback_hours', escalation_hours))}h: "
            f"{escalations.get('recent')} (threshold {max(1, int(escalation_warn_count))})."
        )
    if int(transcription_queue.get("pending", 0)) >= max(1, int(voice_queue_warn_count)):
        warnings.append(
            f"voice transcription queue backlog is high: {transcription_queue.get('pending')} "
            f"(threshold {max(1, int(voice_queue_warn_count))})."
        )

    return {
        "generated_at": _now_iso(),
        "config": {
            "comms_log_stale_minutes": max(1, int(comms_log_stale_minutes)),
            "component_stale_minutes": max(1, int(component_stale_minutes)),
            "escalation_digest_stale_minutes": max(1, int(escalation_digest_stale_minutes)),
            "escalation_hours": max(1, int(escalation_hours)),
            "escalation_warn_count": max(1, int(escalation_warn_count)),
            "voice_queue_warn_count": max(1, int(voice_queue_warn_count)),
            "require_escalation_digest": bool(require_escalation_digest),
            "check_openclaw_channels": bool(check_openclaw_channels),
            "require_openclaw_imessage": bool(require_openclaw_imessage),
        },
        "launchd": launchd,
        "components": {
            "discord_relay": relay,
            "telegram_control": telegram,
            "glasses_autopilot": glasses,
            "integration_readiness": readiness,
            "escalation_digest": escalation_digest,
            "openclaw_channels": openclaw_channels,
        },
        "escalations": escalations,
        "transcription_queue": transcription_queue,
        "latest_logs": {
            "comms_loop_log": str(comms_log) if comms_log else "",
            "comms_loop_log_stale_minutes": stale_minutes,
        },
        "warnings": warnings,
    }


def _write_report(payload: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)

    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"comms_status_{stamp}.md"
    latest_md = OUTPUT_DIR / "comms_status_latest.md"
    json_path = TOOL_DIR / f"comms_status_{stamp}.json"

    launchd = payload.get("launchd") if isinstance(payload.get("launchd"), dict) else {}
    components = payload.get("components") if isinstance(payload.get("components"), dict) else {}
    relay = components.get("discord_relay") if isinstance(components.get("discord_relay"), dict) else {}
    telegram = components.get("telegram_control") if isinstance(components.get("telegram_control"), dict) else {}
    glasses = components.get("glasses_autopilot") if isinstance(components.get("glasses_autopilot"), dict) else {}
    escalation_digest = components.get("escalation_digest") if isinstance(components.get("escalation_digest"), dict) else {}
    openclaw_channels = components.get("openclaw_channels") if isinstance(components.get("openclaw_channels"), dict) else {}
    openclaw_telegram = (
        openclaw_channels.get("telegram") if isinstance(openclaw_channels.get("telegram"), dict) else {}
    )
    openclaw_discord = (
        openclaw_channels.get("discord") if isinstance(openclaw_channels.get("discord"), dict) else {}
    )
    openclaw_imessage = (
        openclaw_channels.get("imessage") if isinstance(openclaw_channels.get("imessage"), dict) else {}
    )
    escalations = payload.get("escalations") if isinstance(payload.get("escalations"), dict) else {}
    transcription_queue = payload.get("transcription_queue") if isinstance(payload.get("transcription_queue"), dict) else {}

    lines = [
        "# Comms Status",
        "",
        f"Generated (UTC): {payload.get('generated_at', _now_iso())}",
        "",
        "## Automation",
        f"- Launchd installed: {bool(launchd.get('installed'))}",
        f"- Launchd state: {launchd.get('state', 'unknown')}",
        f"- Launchd runs: {launchd.get('runs', 0)}",
        f"- Launchd last exit: {launchd.get('last_exit_code')}",
        f"- Launchd interval seconds: {launchd.get('run_interval_seconds')}",
        "",
        "## Components",
        f"- Discord relay: present={bool(relay.get('present'))}, stale_minutes={relay.get('stale_minutes')}, new_messages={relay.get('new_messages')}, telegram_sent={relay.get('telegram_messages_sent')}",
        f"- Telegram control: present={bool(telegram.get('present'))}, stale_minutes={telegram.get('stale_minutes')}, updates={telegram.get('updates_count')}, ingested={telegram.get('ingested_count')}",
        f"- Glasses autopilot: present={bool(glasses.get('present'))}, stale_minutes={glasses.get('stale_minutes')}, imported={glasses.get('imported_count')}, scanned={glasses.get('candidate_count')}",
        f"- Escalation digest: present={bool(escalation_digest.get('present'))}, stale_minutes={escalation_digest.get('stale_minutes')}, telegram_sent={escalation_digest.get('telegram_sent')}, discord_sent={escalation_digest.get('discord_sent')}",
        (
            "- OpenClaw channels: "
            f"probe_invoked={bool(openclaw_channels.get('invoked'))}, "
            f"gateway_reachable={bool(openclaw_channels.get('gateway_reachable'))}, "
            f"telegram_works={bool(openclaw_telegram.get('works'))}, "
            f"discord_works={bool(openclaw_discord.get('works'))}, "
            f"imessage_works={bool(openclaw_imessage.get('works'))}"
        ),
        "",
        "## Escalations",
        f"- Path: {escalations.get('path', '-')}",
        f"- Exists: {bool(escalations.get('exists'))}",
        f"- Total: {escalations.get('total', 0)}",
        f"- Recent ({escalations.get('lookback_hours', 0)}h): {escalations.get('recent', 0)}",
        "",
        "## Voice Transcription Queue",
        f"- Path: {transcription_queue.get('path', '-')}",
        f"- Exists: {bool(transcription_queue.get('exists'))}",
        f"- Pending: {transcription_queue.get('pending', 0)}",
        f"- Done: {transcription_queue.get('done', 0)}",
        f"- Total: {transcription_queue.get('total', 0)}",
        "",
    ]

    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    lines.append("## Warnings")
    if warnings:
        for item in warnings:
            lines.append(f"- {item}")
    else:
        lines.append("- None")

    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comms stack status rollup")
    parser.add_argument(
        "--comms-log-stale-minutes",
        type=int,
        default=int(os.getenv("PERMANENCE_COMMS_STATUS_LOG_STALE_MINUTES", "20")),
        help="Warn when latest comms loop log is older than this many minutes",
    )
    parser.add_argument(
        "--component-stale-minutes",
        type=int,
        default=int(os.getenv("PERMANENCE_COMMS_STATUS_COMPONENT_STALE_MINUTES", "120")),
        help="Warn when core component payloads are older than this many minutes",
    )
    parser.add_argument(
        "--escalation-digest-stale-minutes",
        type=int,
        default=int(os.getenv("PERMANENCE_COMMS_STATUS_ESCALATION_DIGEST_STALE_MINUTES", "1500")),
        help="Warn when escalation digest payload is older than this many minutes",
    )
    parser.add_argument(
        "--escalation-hours",
        type=int,
        default=int(os.getenv("PERMANENCE_COMMS_STATUS_ESCALATION_HOURS", "24")),
        help="Escalation lookback window in hours",
    )
    parser.add_argument(
        "--escalation-warn-count",
        type=int,
        default=int(os.getenv("PERMANENCE_COMMS_STATUS_ESCALATION_WARN_COUNT", "8")),
        help="Warn when escalations in lookback window are >= this value",
    )
    parser.add_argument(
        "--voice-queue-warn-count",
        type=int,
        default=int(os.getenv("PERMANENCE_COMMS_STATUS_VOICE_QUEUE_WARN_COUNT", "15")),
        help="Warn when pending voice transcription queue entries are >= this value",
    )
    parser.add_argument(
        "--require-escalation-digest",
        action="store_true",
        default=_is_true(os.getenv("PERMANENCE_COMMS_STATUS_REQUIRE_ESCALATION_DIGEST", "0")),
        help="Warn when escalation digest payload is missing",
    )
    parser.add_argument(
        "--skip-openclaw-channels-check",
        action="store_true",
        default=not _is_true(os.getenv("PERMANENCE_COMMS_STATUS_CHECK_OPENCLAW_CHANNELS", "1")),
        help="Skip probing OpenClaw Telegram/Discord channel health",
    )
    parser.add_argument(
        "--require-openclaw-imessage",
        action="store_true",
        default=_is_true(os.getenv("PERMANENCE_COMMS_STATUS_REQUIRE_IMESSAGE", "0")),
        help="Treat OpenClaw iMessage as required instead of optional.",
    )
    args = parser.parse_args(argv)

    payload = _build_payload(
        comms_log_stale_minutes=max(1, int(args.comms_log_stale_minutes)),
        component_stale_minutes=max(1, int(args.component_stale_minutes)),
        escalation_digest_stale_minutes=max(1, int(args.escalation_digest_stale_minutes)),
        escalation_hours=max(1, int(args.escalation_hours)),
        escalation_warn_count=max(1, int(args.escalation_warn_count)),
        voice_queue_warn_count=max(1, int(args.voice_queue_warn_count)),
        require_escalation_digest=bool(args.require_escalation_digest),
        check_openclaw_channels=not bool(args.skip_openclaw_channels_check),
        require_openclaw_imessage=bool(args.require_openclaw_imessage),
    )
    md_path, json_path = _write_report(payload)
    print(f"Comms status written: {md_path}")
    print(f"Comms status latest: {OUTPUT_DIR / 'comms_status_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Warnings: {len(payload.get('warnings') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
