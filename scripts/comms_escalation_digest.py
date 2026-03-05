#!/usr/bin/env python3
"""
Build and optionally dispatch a digest of recent communication escalations.
"""

from __future__ import annotations

import argparse
import json
import os
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
ESCALATIONS_PATH = Path(
    os.getenv(
        "PERMANENCE_COMMS_ESCALATIONS_PATH",
        str(WORKING_DIR / "comms" / "escalations.jsonl"),
    )
)
DISCORD_WEBHOOK_ENV = "PERMANENCE_DISCORD_ALERT_WEBHOOK_URL"
TELEGRAM_TOKEN_ENV = "PERMANENCE_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ENV = "PERMANENCE_TELEGRAM_CHAT_ID"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _priority_rank(value: Any) -> int:
    token = str(value or "").strip().lower()
    return {"urgent": 3, "high": 2, "normal": 1, "low": 0}.get(token, 1)


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


def _filter_recent(rows: list[dict[str, Any]], hours: int) -> list[dict[str, Any]]:
    if not rows:
        return []
    cutoff = _now().timestamp() - max(1, int(hours)) * 3600
    picked: list[dict[str, Any]] = []
    for row in rows:
        created_at = str(row.get("created_at") or "").strip()
        ts = 0.0
        if created_at:
            try:
                ts = datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
            except ValueError:
                ts = 0.0
        if ts >= cutoff:
            picked.append(row)
    return picked


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_priority: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_channel: dict[str, int] = {}
    for row in rows:
        priority = str(row.get("priority") or "normal").strip().lower()
        source = str(row.get("source") or "unknown").strip() or "unknown"
        channel = str(row.get("channel") or "discord").strip() or "discord"
        by_priority[priority] = by_priority.get(priority, 0) + 1
        by_source[source] = by_source.get(source, 0) + 1
        by_channel[channel] = by_channel.get(channel, 0) + 1
    return {
        "count": len(rows),
        "by_priority": dict(sorted(by_priority.items(), key=lambda item: (-_priority_rank(item[0]), item[0]))),
        "by_source": dict(sorted(by_source.items(), key=lambda item: (-item[1], item[0]))),
        "by_channel": dict(sorted(by_channel.items(), key=lambda item: (-item[1], item[0]))),
    }


def _build_message(rows: list[dict[str, Any]], *, hours: int, max_items: int) -> str:
    picked = sorted(
        rows,
        key=lambda row: (
            -_priority_rank(row.get("priority")),
            str(row.get("created_at") or ""),
        ),
        reverse=False,
    )[: max(1, int(max_items))]
    stats = _summary(rows)
    lines = [
        f"Comms Escalation Digest ({hours}h)",
        f"total: {stats['count']}",
        "",
        "priority:",
    ]
    by_priority = stats.get("by_priority") if isinstance(stats.get("by_priority"), dict) else {}
    if by_priority:
        for key, value in by_priority.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    lines.extend(["", "latest:"])
    if not picked:
        lines.append("- none")
    for idx, row in enumerate(picked, start=1):
        priority = str(row.get("priority") or "normal").strip().lower()
        source = str(row.get("source") or "Discord").strip()
        sender = str(row.get("sender") or "user").strip()
        message = str(row.get("message") or "").replace("\n", " ").strip()
        if len(message) > 180:
            message = message[:177].rstrip() + "..."
        link = str(row.get("link") or "").strip()
        lines.append(f"{idx}) [{priority}] {source} | {sender}: {message}")
        if link:
            lines.append(link)
    return "\n".join(lines).strip() + "\n"


def _send_telegram(token: str, chat_id: str, text: str, timeout: int) -> bool:
    if not str(token or "").strip() or not str(chat_id or "").strip():
        return False
    response = requests.post(
        f"https://api.telegram.org/bot{str(token).strip()}/sendMessage",
        timeout=max(3, int(timeout)),
        data={"chat_id": str(chat_id).strip(), "text": str(text)[:3900], "disable_web_page_preview": "true"},
        headers={"User-Agent": "permanence-os-comms-escalation-digest"},
    )
    if response.status_code != 200:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    return bool(payload.get("ok"))


def _send_discord(webhook_url: str, text: str, timeout: int) -> bool:
    if not str(webhook_url or "").strip():
        return False
    response = requests.post(
        str(webhook_url).strip(),
        timeout=max(3, int(timeout)),
        json={"content": str(text)[:1900]},
        headers={"User-Agent": "permanence-os-comms-escalation-digest"},
    )
    return 200 <= response.status_code < 300


def _write_report(
    *,
    path: Path,
    hours: int,
    max_items: int,
    rows: list[dict[str, Any]],
    message: str,
    telegram_sent: int,
    discord_sent: int,
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"comms_escalation_digest_{stamp}.md"
    latest_md = OUTPUT_DIR / "comms_escalation_digest_latest.md"
    json_path = TOOL_DIR / f"comms_escalation_digest_{stamp}.json"
    stats = _summary(rows)

    lines = [
        "# Comms Escalation Digest",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Escalations path: {path}",
        f"Hours: {hours}",
        f"Max items: {max_items}",
        "",
        "## Summary",
        f"- Total escalations in window: {stats.get('count', 0)}",
        f"- Telegram sent: {telegram_sent}",
        f"- Discord sent: {discord_sent}",
        f"- Warnings: {len(warnings)}",
        "",
        "## Digest Message",
    ]
    for row in message.strip().splitlines():
        lines.append(f"- {row}")
    if warnings:
        lines.extend(["", "## Warnings"])
        for row in warnings:
            lines.append(f"- {row}")
    lines.append("")

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    payload = {
        "generated_at": _now_iso(),
        "escalations_path": str(path),
        "hours": hours,
        "max_items": max_items,
        "summary": stats,
        "telegram_sent": telegram_sent,
        "discord_sent": discord_sent,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build/send escalation digest")
    parser.add_argument("--escalations-path", help="Escalations JSONL path")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    parser.add_argument("--max-items", type=int, default=8, help="Max escalation rows in digest")
    parser.add_argument("--send", action="store_true", help="Send digest to Telegram and Discord (if configured)")
    parser.add_argument("--send-telegram", action="store_true", help="Send digest to Telegram")
    parser.add_argument("--send-discord", action="store_true", help="Send digest to Discord webhook")
    parser.add_argument("--chat-id", help="Telegram chat id override")
    parser.add_argument("--webhook-url", help="Discord webhook URL override")
    parser.add_argument("--timeout", type=int, default=15, help="Network timeout seconds")
    args = parser.parse_args(argv)

    escalations_path = Path(args.escalations_path).expanduser() if args.escalations_path else ESCALATIONS_PATH
    rows = _read_jsonl(escalations_path)
    recent = _filter_recent(rows, hours=max(1, int(args.hours)))
    message = _build_message(recent, hours=max(1, int(args.hours)), max_items=max(1, int(args.max_items)))
    warnings: list[str] = []

    send_tg = bool(args.send or args.send_telegram)
    send_dc = bool(args.send or args.send_discord)
    telegram_sent = 0
    discord_sent = 0

    if send_tg:
        token = str(os.getenv(TELEGRAM_TOKEN_ENV, "")).strip()
        chat_id = str(args.chat_id or os.getenv(TELEGRAM_CHAT_ENV, "")).strip()
        if _send_telegram(token=token, chat_id=chat_id, text=message, timeout=max(3, int(args.timeout))):
            telegram_sent = 1
        else:
            warnings.append("Telegram send failed or missing token/chat id.")

    if send_dc:
        webhook_url = str(args.webhook_url or os.getenv(DISCORD_WEBHOOK_ENV, "")).strip()
        if _send_discord(webhook_url=webhook_url, text=message, timeout=max(3, int(args.timeout))):
            discord_sent = 1
        else:
            warnings.append("Discord send failed or missing webhook URL.")

    md_path, json_path = _write_report(
        path=escalations_path,
        hours=max(1, int(args.hours)),
        max_items=max(1, int(args.max_items)),
        rows=recent,
        message=message,
        telegram_sent=telegram_sent,
        discord_sent=discord_sent,
        warnings=warnings,
    )
    print(f"Comms escalation digest written: {md_path}")
    print(f"Comms escalation digest latest: {OUTPUT_DIR / 'comms_escalation_digest_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Escalations in window: {len(recent)}")
    print(f"Telegram sent: {telegram_sent}")
    print(f"Discord sent: {discord_sent}")
    if warnings:
        print(f"Warnings: {len(warnings)}")
    return 0 if not warnings else 1


if __name__ == "__main__":
    raise SystemExit(main())
