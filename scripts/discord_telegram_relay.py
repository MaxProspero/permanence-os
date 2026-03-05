#!/usr/bin/env python3
"""
Relay new Discord channel messages into Telegram.

Flow:
- Reads Discord feeds from social_research_feeds.json
- Pulls only enabled Discord rows with channel_id
- Tracks per-channel last_message_id state to avoid duplicates
- Sends concise digest chunks to Telegram bot chat
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))


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
STATE_PATH = Path(
    os.getenv(
        "PERMANENCE_DISCORD_TELEGRAM_RELAY_STATE_PATH",
        str(WORKING_DIR / "discord_telegram_relay" / "state.json"),
    )
)
ESCALATIONS_PATH = Path(
    os.getenv(
        "PERMANENCE_COMMS_ESCALATIONS_PATH",
        str(WORKING_DIR / "comms" / "escalations.jsonl"),
    )
)
INTAKE_PATH = Path(
    os.getenv(
        "PERMANENCE_DISCORD_RELAY_INTAKE_PATH",
        str(WORKING_DIR.parent / "inbox" / "telegram_share_intake.jsonl"),
    )
)
DISCORD_TOKEN_ENV = "PERMANENCE_DISCORD_BOT_TOKEN"
DISCORD_WEBHOOK_ENV = "PERMANENCE_DISCORD_ALERT_WEBHOOK_URL"
TELEGRAM_TOKEN_ENV = "PERMANENCE_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ENV = "PERMANENCE_TELEGRAM_CHAT_ID"


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _snowflake_gt(left: str, right: str) -> bool:
    left = str(left or "").strip()
    right = str(right or "").strip()
    if not left:
        return False
    if not right:
        return True
    try:
        return int(left) > int(right)
    except ValueError:
        return left > right


def _discord_limit(value: Any, default: int = 30) -> int:
    return max(1, min(100, _safe_int(value, default)))


def _parse_keywords(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = [str(item or "") for item in value]
    else:
        raw = str(value or "").split(",")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        token = item.strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _normalize_priority(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"urgent", "high", "normal", "low"}:
        return token
    return "normal"


def _priority_rank(value: Any) -> int:
    token = _normalize_priority(value)
    return {"urgent": 3, "high": 2, "normal": 1, "low": 0}.get(token, 1)


def _discord_feeds(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("platform") or "").lower() != "discord":
            continue
        if isinstance(row.get("enabled"), bool) and not bool(row.get("enabled")):
            continue
        channel_id = str(row.get("channel_id") or "").strip()
        if not channel_id:
            continue
        out.append(row)
    return out


def _passes_feed_filters(message: dict[str, Any], feed: dict[str, Any]) -> bool:
    content = str(message.get("content") or "").strip()
    content_lower = content.lower()
    min_chars = max(0, _safe_int(feed.get("min_chars"), 0))
    if min_chars > 0 and len(content) < min_chars:
        return False
    include_keywords = _parse_keywords(feed.get("include_keywords"))
    if include_keywords and not any(token in content_lower for token in include_keywords):
        return False
    exclude_keywords = _parse_keywords(feed.get("exclude_keywords"))
    if exclude_keywords and any(token in content_lower for token in exclude_keywords):
        return False
    return True


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _escalation_key(row: dict[str, Any]) -> str:
    return f"{str(row.get('channel_id') or '').strip()}:{str(row.get('message_id') or '').strip()}"


def _load_existing_escalation_keys(path: Path, tail_rows: int = 5000) -> set[str]:
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows = lines[-max(1, int(tail_rows)) :]
    keys: set[str] = set()
    for line in rows:
        token = line.strip()
        if not token:
            continue
        try:
            payload = json.loads(token)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        key = _escalation_key(payload)
        if key != ":":
            keys.add(key)
    return keys


def _intake_key(row: dict[str, Any]) -> str:
    channel_id = str(row.get("channel_id") or "").strip()
    message_id = str(row.get("message_id") or "").strip()
    if channel_id and message_id:
        return f"discord:{channel_id}:{message_id}"
    return ""


def _load_existing_intake_keys(path: Path, tail_rows: int = 5000) -> set[str]:
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    rows = lines[-max(1, int(tail_rows)) :]
    keys: set[str] = set()
    for line in rows:
        token = line.strip()
        if not token:
            continue
        try:
            payload = json.loads(token)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        key = str(payload.get("intake_id") or "").strip()
        if key:
            keys.add(key)
    return keys


def _mirror_messages_to_intake(messages: list[dict[str, Any]], intake_path: Path) -> int:
    if not messages:
        return 0
    existing = _load_existing_intake_keys(intake_path)
    mirrored = 0
    for row in messages:
        intake_id = _intake_key(row)
        if not intake_id or intake_id in existing:
            continue
        source = str(row.get("source") or "Discord").strip()
        sender = str(row.get("sender") or "discord").strip()
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        link = str(row.get("link") or "").strip()
        feed_priority = _normalize_priority(row.get("feed_priority"))
        text = f"[Discord|{source}|{feed_priority}] {sender}: {content}"
        if link:
            text = f"{text}\n{link}"
        payload = {
            "intake_id": intake_id,
            "timestamp": _now_iso(),
            "chat_id": f"discord:{str(row.get('channel_id') or '').strip()}",
            "sender_user_id": "",
            "sender": sender,
            "source": "discord-telegram-relay",
            "text": text,
            "char_count": len(text),
        }
        _append_jsonl(intake_path, payload)
        existing.add(intake_id)
        mirrored += 1
    return mirrored


def _should_escalate(
    message: dict[str, Any],
    feed: dict[str, Any],
    default_keywords: list[str],
    min_priority: str,
) -> bool:
    content = str(message.get("content") or "").strip().lower()
    if not content:
        return False
    feed_priority = _normalize_priority(feed.get("priority"))
    if _priority_rank(feed_priority) < _priority_rank(min_priority):
        return False
    feed_keywords = _parse_keywords(feed.get("escalation_keywords"))
    keywords = feed_keywords or default_keywords
    if not keywords:
        return False
    return any(token in content for token in keywords)


def _escalate_to_reception(escalation: dict[str, Any], queue_dir: Path) -> bool:
    try:
        from agents.departments.reception_agent import ReceptionAgent  # noqa: WPS433
    except Exception:
        return False
    agent = ReceptionAgent()
    result = agent.execute(
        {
            "action": "intake",
            "queue_dir": str(queue_dir),
            "sender": str(escalation.get("sender") or "discord-relay"),
            "message": str(escalation.get("message") or ""),
            "channel": str(escalation.get("channel") or "discord"),
            "source": "discord-telegram-relay",
            "priority": str(escalation.get("priority") or "urgent"),
        }
    )
    return result.status == "INTAKE_SAVED"


def _build_escalation_message(rows: list[dict[str, Any]], max_items: int = 5) -> str:
    picked = rows[: max(1, int(max_items))]
    lines = [
        f"Discord Escalations ({_now().strftime('%Y-%m-%d %H:%M UTC')})",
        f"items: {len(picked)}",
        "",
    ]
    for idx, row in enumerate(picked, start=1):
        source = str(row.get("source") or "Discord").strip()
        priority = _normalize_priority(row.get("priority"))
        sender = str(row.get("sender") or "user").strip()
        message = str(row.get("message") or "").strip()
        if len(message) > 180:
            message = message[:177].rstrip() + "..."
        link = str(row.get("link") or "").strip()
        lines.append(f"{idx}) [{priority}] {source} | {sender}: {message}")
        if link:
            lines.append(link)
    return "\n".join(lines).strip() + "\n"


def _send_discord_webhook(url: str, message: str, timeout: int = 15) -> bool:
    if not str(url or "").strip():
        return False
    response = requests.post(
        str(url).strip(),
        timeout=max(3, int(timeout)),
        json={"content": str(message)[:1900]},
        headers={"User-Agent": "permanence-os-discord-telegram-relay"},
    )
    return 200 <= response.status_code < 300


def _send_telegram_text(token: str, chat_id: str, message: str, timeout: int = 15) -> bool:
    if not str(token or "").strip() or not str(chat_id or "").strip():
        return False
    payload = _telegram_api(
        token=str(token).strip(),
        method="sendMessage",
        params={"chat_id": str(chat_id).strip(), "text": str(message)[:3900]},
        timeout=max(3, int(timeout)),
    )
    return bool(payload.get("ok"))


def _fetch_discord_messages(
    *,
    token: str,
    channel_id: str,
    limit: int,
    after_id: str,
    timeout: int,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": _discord_limit(limit)}
    if after_id:
        params["after"] = after_id
    response = requests.get(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        timeout=max(5, int(timeout)),
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "permanence-os-discord-telegram-relay",
        },
        params=params,
    )
    if response.status_code == 401:
        raise RuntimeError("Discord API returned 401 Unauthorized. Regenerate PERMANENCE_DISCORD_BOT_TOKEN.")
    if response.status_code == 403:
        raise RuntimeError("Discord API returned 403 Forbidden. Ensure bot has channel read permissions.")
    if response.status_code == 404:
        raise RuntimeError("Discord API returned 404 Channel Not Found. Verify channel_id.")
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


def _extract_message(
    item: dict[str, Any],
    source_name: str,
    channel_id: str,
    *,
    feed_priority: str = "normal",
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    message_id = str(item.get("id") or "").strip()
    if not message_id:
        return None

    content = str(item.get("content") or "").replace("\r", " ").replace("\n", " ").strip()
    attachments = item.get("attachments") if isinstance(item.get("attachments"), list) else []
    if not content and attachments:
        labels: list[str] = []
        for att in attachments[:4]:
            if not isinstance(att, dict):
                continue
            filename = str(att.get("filename") or "").strip()
            url = str(att.get("url") or "").strip()
            labels.append(filename or url)
        if labels:
            content = "attachments: " + ", ".join(labels)

    if not content:
        embeds = item.get("embeds") if isinstance(item.get("embeds"), list) else []
        embed_titles = [str(embed.get("title") or "").strip() for embed in embeds if isinstance(embed, dict)]
        embed_titles = [t for t in embed_titles if t]
        if embed_titles:
            content = "embeds: " + ", ".join(embed_titles[:3])

    if not content:
        return None

    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    sender = (
        str(author.get("global_name") or "").strip()
        or str(author.get("username") or "").strip()
        or "discord"
    )

    guild_id = str(item.get("guild_id") or "").strip()
    link = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}" if guild_id else ""

    return {
        "source": source_name,
        "platform": "discord",
        "channel_id": channel_id,
        "message_id": message_id,
        "sender": sender,
        "content": content,
        "timestamp": str(item.get("timestamp") or ""),
        "link": link,
        "feed_priority": _normalize_priority(feed_priority),
    }


def _sort_messages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            -_priority_rank(row.get("feed_priority")),
            int(str(row.get("message_id") or "0")),
        ),
    )


def _build_digest(messages: list[dict[str, Any]], max_chars_per_line: int = 280) -> str:
    if not messages:
        return ""
    lines = [
        f"Discord relay ({_now_iso()})",
        f"New messages: {len(messages)}",
        "",
    ]
    for row in messages:
        source = str(row.get("source") or "Discord")
        feed_priority = _normalize_priority(row.get("feed_priority"))
        sender = str(row.get("sender") or "user")
        content = str(row.get("content") or "").strip()
        if len(content) > max(40, int(max_chars_per_line)):
            content = content[: max(40, int(max_chars_per_line)) - 3].rstrip() + "..."
        link = str(row.get("link") or "").strip()
        lines.append(f"[{source}|{feed_priority}] {sender}: {content}")
        if link:
            lines.append(link)
    return "\n".join(lines).strip() + "\n"


def _split_chunks(text: str, max_chars: int = 3500) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if current and size + line_len > max_chars:
            chunks.append("\n".join(current).strip() + "\n")
            current = [line]
            size = line_len
        else:
            current.append(line)
            size += line_len
    if current:
        chunks.append("\n".join(current).strip() + "\n")
    return chunks


def _telegram_api(token: str, method: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    cmd = ["curl", "-sS", "--max-time", str(max(1, int(timeout))), url]
    for key, value in params.items():
        cmd.extend(["--data-urlencode", f"{key}={value}"])
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"curl exited {proc.returncode}")
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise RuntimeError(f"Invalid JSON response from Telegram API: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Telegram API payload shape")
    return payload


def _send_telegram_messages(
    *,
    token: str,
    chat_id: str,
    chunks: list[str],
    timeout: int,
) -> int:
    sent = 0
    for idx, chunk in enumerate(chunks, start=1):
        prefix = f"[{idx}/{len(chunks)}]\n" if len(chunks) > 1 else ""
        payload = _telegram_api(
            token=token,
            method="sendMessage",
            params={"chat_id": chat_id, "text": prefix + chunk},
            timeout=timeout,
        )
        if not bool(payload.get("ok")):
            raise RuntimeError(f"Telegram sendMessage returned ok=false at chunk {idx}")
        sent += 1
    return sent


def _write_report(
    *,
    action: str,
    feeds_path: Path,
    state_path: Path,
    active_feeds: int,
    new_messages: int,
    filtered_messages: int,
    escalations: int,
    reception_escalations: int,
    escalation_telegram_sent: int,
    escalation_discord_sent: int,
    escalation_path: Path,
    telegram_sent: int,
    intake_mirrored: int,
    intake_path: Path,
    dry_run: bool,
    warnings: list[str],
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"discord_telegram_relay_{stamp}.md"
    latest_md = OUTPUT_DIR / "discord_telegram_relay_latest.md"
    json_path = TOOL_DIR / f"discord_telegram_relay_{stamp}.json"

    lines = [
        "# Discord Telegram Relay",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        f"Feeds path: {feeds_path}",
        f"State path: {state_path}",
        "",
        "## Summary",
        f"- Active Discord feeds: {active_feeds}",
        f"- New Discord messages: {new_messages}",
        f"- Filtered Discord messages: {filtered_messages}",
        f"- Escalations: {escalations}",
        f"- Reception escalations: {reception_escalations}",
        f"- Escalation Telegram sends: {escalation_telegram_sent}",
        f"- Escalation Discord sends: {escalation_discord_sent}",
        f"- Escalations path: {escalation_path}",
        f"- Telegram messages sent: {telegram_sent}",
        f"- Intake mirrored messages: {intake_mirrored}",
        f"- Intake path: {intake_path}",
        f"- Dry run: {dry_run}",
        f"- Warnings: {len(warnings)}",
        "",
    ]
    if warnings:
        lines.append("## Warnings")
        for item in warnings[:100]:
            lines.append(f"- {item}")
        lines.append("")

    report = "\n".join(lines)
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "feeds_path": str(feeds_path),
        "state_path": str(state_path),
        "active_feeds": active_feeds,
        "new_messages": new_messages,
        "filtered_messages": filtered_messages,
        "escalations": escalations,
        "reception_escalations": reception_escalations,
        "escalation_telegram_sent": escalation_telegram_sent,
        "escalation_discord_sent": escalation_discord_sent,
        "escalation_path": str(escalation_path),
        "telegram_messages_sent": telegram_sent,
        "intake_mirrored": intake_mirrored,
        "intake_path": str(intake_path),
        "dry_run": dry_run,
        "warnings": warnings,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relay Discord feed messages into Telegram")
    parser.add_argument("--action", choices=["status", "run"], default="status")
    parser.add_argument("--feeds-path", help="Discord feeds JSON path")
    parser.add_argument("--state-path", help="State JSON path")
    parser.add_argument("--chat-id", help="Telegram chat/channel id")
    parser.add_argument("--max-per-feed", type=int, default=20, help="Max messages pulled per feed")
    parser.add_argument("--timeout", type=int, default=20, help="Network timeout seconds")
    parser.add_argument("--escalate", action="store_true", help="Enable keyword-based escalation")
    parser.add_argument("--no-escalate", action="store_true", help="Disable escalation even if env default enables it")
    parser.add_argument("--escalation-keyword", action="append", default=[], help="Escalation keyword (repeatable)")
    parser.add_argument(
        "--escalation-min-priority",
        choices=["urgent", "high", "normal", "low"],
        default=str(os.getenv("PERMANENCE_DISCORD_RELAY_ESCALATION_MIN_PRIORITY", "high")).strip().lower() or "high",
        help="Minimum feed priority required for escalation checks",
    )
    parser.add_argument("--escalations-path", help="Path to write escalation jsonl")
    parser.add_argument("--escalate-to-reception", dest="escalate_to_reception", action="store_true")
    parser.add_argument("--no-escalate-to-reception", dest="escalate_to_reception", action="store_false")
    parser.add_argument("--escalation-notify", dest="escalation_notify", action="store_true")
    parser.add_argument("--no-escalation-notify", dest="escalation_notify", action="store_false")
    parser.add_argument(
        "--escalation-telegram-min-priority",
        choices=["urgent", "high", "normal", "low"],
        default=str(os.getenv("PERMANENCE_DISCORD_RELAY_ESCALATION_TELEGRAM_MIN_PRIORITY", "high")).strip().lower()
        or "high",
    )
    parser.add_argument(
        "--escalation-discord-min-priority",
        choices=["urgent", "high", "normal", "low"],
        default=str(os.getenv("PERMANENCE_DISCORD_RELAY_ESCALATION_DISCORD_MIN_PRIORITY", "urgent")).strip().lower()
        or "urgent",
    )
    parser.add_argument("--escalation-max-notify", type=int, default=5, help="Max escalation rows in notification")
    parser.add_argument("--escalation-webhook-url", help="Discord webhook override for escalation notifications")
    parser.add_argument("--escalation-notify-timeout", type=int, default=15, help="Notification timeout seconds")
    parser.add_argument("--intake-path", help="Shared intake JSONL path for mirrored Discord messages")
    parser.add_argument("--no-intake-mirror", action="store_true", help="Disable mirroring Discord rows into shared intake")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only, no Telegram send")
    parser.add_argument("--no-commit-state", action="store_true", help="Do not persist last message ids")
    parser.set_defaults(
        escalate_to_reception=_is_true(os.getenv("PERMANENCE_DISCORD_RELAY_ESCALATE_TO_RECEPTION", "1")),
        escalation_notify=_is_true(os.getenv("PERMANENCE_DISCORD_RELAY_ESCALATION_NOTIFY", "1")),
    )
    args = parser.parse_args(argv)

    feeds_path = Path(args.feeds_path).expanduser() if args.feeds_path else FEEDS_PATH
    state_path = Path(args.state_path).expanduser() if args.state_path else STATE_PATH
    escalations_path = Path(args.escalations_path).expanduser() if args.escalations_path else ESCALATIONS_PATH
    intake_path = Path(args.intake_path).expanduser() if args.intake_path else INTAKE_PATH
    intake_mirror_enabled = _is_true(os.getenv("PERMANENCE_DISCORD_RELAY_INTAKE_MIRROR", "1")) and not bool(
        args.no_intake_mirror
    )

    discord_token = str(os.getenv(DISCORD_TOKEN_ENV, "")).strip()
    discord_webhook_url = str(args.escalation_webhook_url or os.getenv(DISCORD_WEBHOOK_ENV, "")).strip()
    telegram_token = str(os.getenv(TELEGRAM_TOKEN_ENV, "")).strip()
    chat_id = str(args.chat_id or os.getenv(TELEGRAM_CHAT_ENV, "")).strip()

    rows_payload = _read_json(feeds_path, [])
    rows = rows_payload if isinstance(rows_payload, list) else []
    feeds = _discord_feeds([row for row in rows if isinstance(row, dict)])

    if args.action == "status":
        print(f"Discord token present: {'yes' if bool(discord_token) else 'no'}")
        print(f"Discord webhook present: {'yes' if bool(discord_webhook_url) else 'no'}")
        print(f"Telegram token present: {'yes' if bool(telegram_token) else 'no'}")
        print(f"Telegram chat configured: {'yes' if bool(chat_id) else 'no'}")
        print(f"Active Discord feeds: {len(feeds)}")
        for feed in feeds[:20]:
            print(f"- {feed.get('name', 'Discord feed')} | channel_id={feed.get('channel_id', '')}")
        return 0

    if not discord_token:
        print(f"Missing {DISCORD_TOKEN_ENV}")
        return 1
    if not args.dry_run:
        if not telegram_token:
            print(f"Missing {TELEGRAM_TOKEN_ENV}")
            return 1
        if not chat_id:
            print(f"Missing --chat-id and {TELEGRAM_CHAT_ENV}")
            return 1

    state = _read_json(state_path, {"channels": {}, "updated_at": ""})
    if not isinstance(state, dict):
        state = {"channels": {}, "updated_at": ""}
    channels_state = state.get("channels") if isinstance(state.get("channels"), dict) else {}

    warnings: list[str] = []
    messages: list[dict[str, Any]] = []
    filtered_messages = 0
    escalations: list[dict[str, Any]] = []
    reception_escalations = 0
    escalation_telegram_sent = 0
    escalation_discord_sent = 0
    updated_state = dict(channels_state)
    escalate_enabled_default = _is_true(os.getenv("PERMANENCE_DISCORD_RELAY_ESCALATE", "1"))
    escalate_enabled = bool(args.escalate or (escalate_enabled_default and not args.no_escalate))
    default_escalation_keywords = _parse_keywords(args.escalation_keyword or [])
    if not default_escalation_keywords:
        default_escalation_keywords = _parse_keywords(os.getenv("PERMANENCE_COMMS_ESCALATION_KEYWORDS", ""))
    existing_escalation_keys = _load_existing_escalation_keys(escalations_path)
    new_escalation_keys: set[str] = set()

    for feed in feeds:
        source_name = str(feed.get("name") or "Discord")
        feed_priority = _normalize_priority(feed.get("priority"))
        channel_id = str(feed.get("channel_id") or "").strip()
        if not channel_id:
            continue
        previous = updated_state.get(channel_id) if isinstance(updated_state.get(channel_id), dict) else {}
        after_id = str((previous or {}).get("last_message_id") or "").strip()
        limit = _discord_limit(feed.get("max_messages", args.max_per_feed), args.max_per_feed)
        limit = min(limit, _discord_limit(args.max_per_feed, args.max_per_feed))

        try:
            raw_messages = _fetch_discord_messages(
                token=discord_token,
                channel_id=channel_id,
                limit=limit,
                after_id=after_id,
                timeout=max(5, int(args.timeout)),
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{source_name}: {exc}")
            continue

        latest_id = after_id
        feed_messages: list[dict[str, Any]] = []
        for item in raw_messages:
            parsed = _extract_message(
                item,
                source_name=source_name,
                channel_id=channel_id,
                feed_priority=feed_priority,
            )
            if parsed is not None:
                if _passes_feed_filters(parsed, feed):
                    feed_messages.append(parsed)
                    if escalate_enabled and _should_escalate(
                        parsed,
                        feed=feed,
                        default_keywords=default_escalation_keywords,
                        min_priority=args.escalation_min_priority,
                    ):
                        escalation = {
                            "created_at": _now_iso(),
                            "source": source_name,
                            "channel_id": channel_id,
                            "message_id": parsed.get("message_id"),
                            "sender": parsed.get("sender"),
                            "message": parsed.get("content"),
                            "link": parsed.get("link"),
                            "priority": feed_priority,
                            "feed_priority": feed_priority,
                            "channel": "discord",
                        }
                        key = _escalation_key(escalation)
                        if key not in existing_escalation_keys and key not in new_escalation_keys:
                            escalations.append(escalation)
                            new_escalation_keys.add(key)
                else:
                    filtered_messages += 1
            message_id = str(item.get("id") or "").strip() if isinstance(item, dict) else ""
            if _snowflake_gt(message_id, latest_id):
                latest_id = message_id

        if latest_id and _snowflake_gt(latest_id, after_id):
            updated_state[channel_id] = {
                "last_message_id": latest_id,
                "updated_at": _now_iso(),
                "source": source_name,
            }

        if feed_messages:
            messages.extend(_sort_messages(feed_messages))

    if escalate_enabled and escalations and not args.dry_run:
        for row in escalations:
            _append_jsonl(escalations_path, row)
        if bool(args.escalate_to_reception):
            queue_dir = Path(
                os.getenv("PERMANENCE_RECEPTION_QUEUE_DIR", str(WORKING_DIR / "reception"))
            ).expanduser()
            for row in escalations:
                if _escalate_to_reception(row, queue_dir=queue_dir):
                    reception_escalations += 1
                else:
                    warnings.append("escalation reception intake failed for one item")
        if bool(args.escalation_notify):
            sorted_escalations = sorted(
                escalations,
                key=lambda row: (
                    -_priority_rank(row.get("priority")),
                    int(str(row.get("message_id") or "0")),
                ),
            )
            tg_min = _priority_rank(args.escalation_telegram_min_priority)
            dc_min = _priority_rank(args.escalation_discord_min_priority)
            tg_rows = [row for row in sorted_escalations if _priority_rank(row.get("priority")) >= tg_min]
            dc_rows = [row for row in sorted_escalations if _priority_rank(row.get("priority")) >= dc_min]
            if tg_rows:
                try:
                    if _send_telegram_text(
                        token=telegram_token,
                        chat_id=chat_id,
                        message=_build_escalation_message(tg_rows, max_items=max(1, int(args.escalation_max_notify))),
                        timeout=max(3, int(args.escalation_notify_timeout)),
                    ):
                        escalation_telegram_sent = 1
                    else:
                        warnings.append("escalation Telegram notify failed")
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"escalation Telegram notify failed: {exc}")
            if dc_rows:
                try:
                    if _send_discord_webhook(
                        url=discord_webhook_url,
                        message=_build_escalation_message(dc_rows, max_items=max(1, int(args.escalation_max_notify))),
                        timeout=max(3, int(args.escalation_notify_timeout)),
                    ):
                        escalation_discord_sent = 1
                    else:
                        warnings.append("escalation Discord notify failed")
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"escalation Discord notify failed: {exc}")

    messages = _sort_messages(messages)
    digest = _build_digest(messages)
    telegram_sent = 0
    intake_mirrored = 0
    relay_ok = True

    if messages and not args.dry_run and intake_mirror_enabled:
        try:
            intake_mirrored = _mirror_messages_to_intake(messages, intake_path=intake_path)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"intake mirror failed: {exc}")

    if messages and not args.dry_run:
        try:
            chunks = _split_chunks(digest)
            telegram_sent = _send_telegram_messages(
                token=telegram_token,
                chat_id=chat_id,
                chunks=chunks,
                timeout=max(5, int(args.timeout)),
            )
        except Exception as exc:  # noqa: BLE001
            relay_ok = False
            warnings.append(f"telegram send failed: {exc}")

    if not args.no_commit_state and relay_ok:
        _write_json(
            state_path,
            {
                "channels": updated_state,
                "updated_at": _now_iso(),
                "last_run_new_messages": len(messages),
            },
        )

    md_path, json_path = _write_report(
        action=args.action,
        feeds_path=feeds_path,
        state_path=state_path,
        active_feeds=len(feeds),
        new_messages=len(messages),
        filtered_messages=filtered_messages,
        escalations=len(escalations),
        reception_escalations=reception_escalations,
        escalation_telegram_sent=escalation_telegram_sent,
        escalation_discord_sent=escalation_discord_sent,
        escalation_path=escalations_path,
        telegram_sent=telegram_sent,
        intake_mirrored=intake_mirrored,
        intake_path=intake_path,
        dry_run=bool(args.dry_run),
        warnings=warnings,
    )
    print(f"Discord Telegram relay written: {md_path}")
    print(f"Discord Telegram relay latest: {OUTPUT_DIR / 'discord_telegram_relay_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print(f"Active Discord feeds: {len(feeds)}")
    print(f"New Discord messages: {len(messages)}")
    print(f"Filtered Discord messages: {filtered_messages}")
    print(f"Escalations: {len(escalations)}")
    print(f"Reception escalations: {reception_escalations}")
    print(f"Escalation Telegram sends: {escalation_telegram_sent}")
    print(f"Escalation Discord sends: {escalation_discord_sent}")
    print(f"Telegram messages sent: {telegram_sent}")
    print(f"Intake mirrored messages: {intake_mirrored}")
    if warnings:
        print(f"Warnings: {len(warnings)}")

    return 0 if relay_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
