#!/usr/bin/env python3
"""
Integration readiness checks for external dependencies and credentials.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
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
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))


@dataclass(frozen=True)
class Check:
    key: str
    required: bool
    kind: str
    help_text: str


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_env(name: str) -> str:
    defaults = {
        "PERMANENCE_GMAIL_CREDENTIALS": str(WORKING_DIR / "google" / "credentials.json"),
        "PERMANENCE_GMAIL_TOKEN": str(WORKING_DIR / "google" / "token.json"),
    }
    return defaults.get(name, "")


def _normalize_value(raw: str, key: str) -> str:
    value = (raw or "").strip()
    if value:
        return value
    if key in {"PERMANENCE_BOOKING_LINK", "PERMANENCE_PAYMENT_LINK"}:
        playbook_path = WORKING_DIR / "revenue_playbook.json"
        if playbook_path.exists():
            try:
                payload = json.loads(playbook_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                if key == "PERMANENCE_BOOKING_LINK":
                    return str(payload.get("booking_link") or "").strip()
                if key == "PERMANENCE_PAYMENT_LINK":
                    return str(payload.get("payment_link") or "").strip()
    return _default_env(key)


def _value_preview(check: Check, value: str) -> str:
    if not value:
        return ""
    key_upper = check.key.upper()
    if check.kind == "secret":
        return "(set)"
    if any(marker in key_upper for marker in ("TOKEN", "KEY", "SECRET", "WEBHOOK", "PASSWORD")):
        return "(set)"
    if check.kind == "url":
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            return "(set)"
        return f"{parsed.scheme}://{parsed.netloc}"
    return value[:120]


def _check_item(check: Check) -> dict[str, Any]:
    raw = os.environ.get(check.key, "")
    value = _normalize_value(raw, check.key)
    exists = False
    if check.kind == "path":
        exists = bool(value) and Path(os.path.expanduser(value)).exists()
    elif check.kind == "command":
        exists = bool(value) and shutil.which(value) is not None
    elif check.kind == "url":
        exists = value.startswith("http://") or value.startswith("https://")
    else:
        exists = bool(value)

    status = "ready" if exists else ("missing" if check.required else "optional_missing")
    return {
        "key": check.key,
        "required": check.required,
        "kind": check.kind,
        "status": status,
        "exists": exists,
        "value_present": bool(value),
        "value_preview": _value_preview(check, value),
        "help": check.help_text,
    }


def _is_true(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _require_revenue_links() -> bool:
    raw = str(os.getenv("PERMANENCE_REQUIRE_REVENUE_LINKS", "0"))
    return _is_true(raw)


def _model_provider() -> str:
    raw = str(os.getenv("PERMANENCE_MODEL_PROVIDER", "anthropic")).strip().lower()
    if raw in {"claude", "anthropic"}:
        return "anthropic"
    if raw in {"openai", "gpt"}:
        return "openai"
    if raw in {"xai", "grok"}:
        return "xai"
    if raw in {"ollama", "local", "qwen"}:
        return "ollama"
    return "anthropic"


def _checks() -> list[Check]:
    require_revenue_links = _require_revenue_links()
    model_provider = _model_provider()
    anthropic_required = model_provider == "anthropic"
    openai_required = model_provider == "openai"
    xai_required = model_provider == "xai"
    return [
        Check(
            "PERMANENCE_MODEL_PROVIDER",
            False,
            "text",
            "Primary model provider for routing (anthropic/openai/xai/ollama).",
        ),
        Check(
            "ANTHROPIC_API_KEY",
            anthropic_required,
            "secret",
            "Required when PERMANENCE_MODEL_PROVIDER=anthropic.",
        ),
        Check("PERMANENCE_GMAIL_CREDENTIALS", True, "path", "Google OAuth client credentials JSON."),
        Check("PERMANENCE_GMAIL_TOKEN", True, "path", "Google OAuth token JSON (run gmail-ingest once to authorize)."),
        Check("PERMANENCE_BOOKING_LINK", require_revenue_links, "url", "Booking link used in outreach and offers."),
        Check("PERMANENCE_PAYMENT_LINK", require_revenue_links, "url", "Payment link used in proposals and close flow."),
        Check("PERMANENCE_SLACK_WEBHOOK_URL", False, "url", "Optional Slack notifications."),
        Check("PERMANENCE_GITHUB_READ_TOKEN", False, "secret", "Optional read-only token for GitHub research ingest."),
        Check("PERMANENCE_SOCIAL_READ_TOKEN", False, "secret", "Optional read-only token for social trend ingest."),
        Check("PERMANENCE_DISCORD_ALERT_WEBHOOK_URL", False, "url", "Optional Discord webhook for world-watch alerts."),
        Check("PERMANENCE_DISCORD_BOT_TOKEN", False, "secret", "Optional Discord bot token for read-only server research feeds."),
        Check("PERMANENCE_TELEGRAM_BOT_TOKEN", False, "secret", "Optional Telegram bot token for world-watch alerts."),
        Check("PERMANENCE_TELEGRAM_CHAT_ID", False, "text", "Optional Telegram chat id for world-watch alerts."),
        Check("PERMANENCE_HOME_LAT", False, "text", "Optional home latitude to anchor local weather alerts."),
        Check("PERMANENCE_HOME_LON", False, "text", "Optional home longitude to anchor local weather alerts."),
        Check("PERMANENCE_HOME_LABEL", False, "text", "Optional human-friendly home location label for alerts."),
        Check(
            "PERMANENCE_AGENT_EXTERNAL_WRITE_ENABLE",
            False,
            "text",
            "Keep 0/false during research phase; enable only with manual approval queue.",
        ),
        Check(
            "PERMANENCE_WORLD_WATCH_ENABLE",
            False,
            "text",
            "Set to 1 to include world-watch automation in your daily loops.",
        ),
        Check(
            "PERMANENCE_REQUIRE_REVENUE_LINKS",
            False,
            "text",
            "Set to 1 only when you are actively running booking/payment outreach flows.",
        ),
        Check("OPENAI_API_KEY", openai_required, "secret", "Required when PERMANENCE_MODEL_PROVIDER=openai."),
        Check("XAI_API_KEY", xai_required, "secret", "Required when PERMANENCE_MODEL_PROVIDER=xai."),
        Check(
            "PERMANENCE_OLLAMA_BASE_URL",
            False,
            "url",
            "Optional Ollama endpoint (defaults to http://127.0.0.1:11434).",
        ),
        Check("GH_TOKEN", False, "secret", "Optional for GitHub automation."),
        Check("NOTION_API_KEY", False, "secret", "Optional Notion integration secret for THE LEDGER MCP."),
        Check("NOTION_LEDGER_DB_ID", False, "text", "Optional Notion database ID for THE LEDGER sync."),
        Check("BRAVE_API_KEY", False, "secret", "Optional Brave Search API key for web search MCP."),
        Check("ALPHA_VANTAGE_API_KEY", False, "secret", "Optional higher-coverage equities and FX intraday data."),
        Check("FINNHUB_API_KEY", False, "secret", "Optional equities/news/sentiment market data API."),
        Check("POLYGON_API_KEY", False, "secret", "Optional institutional-grade US market data API."),
        Check("COINMARKETCAP_API_KEY", False, "secret", "Optional crypto market breadth API."),
        Check("GLASSNODE_API_KEY", False, "secret", "Optional on-chain crypto intelligence API."),
        Check("claude", False, "command", "Optional Claude CLI for terminal workflows."),
    ]


def _write_report(results: list[dict[str, Any]]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"integration_readiness_{stamp}.md"
    latest_md = OUTPUT_DIR / "integration_readiness_latest.md"
    json_path = TOOL_DIR / f"integration_readiness_{stamp}.json"

    required_total = sum(1 for r in results if r["required"])
    required_ready = sum(1 for r in results if r["required"] and r["exists"])
    missing_required = [r for r in results if r["required"] and not r["exists"]]

    lines = [
        "# Integration Readiness",
        "",
        f"Generated (UTC): {_now_utc()}",
        "",
        "## Summary",
        f"- Required ready: {required_ready}/{required_total}",
        f"- Overall status: {'READY' if not missing_required else 'BLOCKED'}",
        "",
        "## Checks",
    ]
    for row in results:
        status = str(row["status"]).upper()
        req = "required" if row["required"] else "optional"
        detail = row["value_preview"] or "(empty)"
        lines.append(f"- {row['key']} | {req} | {status} | {detail}")

    if missing_required:
        lines.extend(["", "## Actions Needed"])
        for row in missing_required:
            lines.append(f"- Set `{row['key']}`: {row['help']}")

    payload = {
        "generated_at": _now_utc(),
        "required_total": required_total,
        "required_ready": required_ready,
        "blocked": bool(missing_required),
        "checks": results,
        "latest_markdown": str(latest_md),
    }
    report = "\n".join(lines) + "\n"
    md_path.write_text(report, encoding="utf-8")
    latest_md.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main() -> int:
    results = [_check_item(check) for check in _checks()]
    md_path, json_path = _write_report(results)
    blocked = any(row["required"] and not row["exists"] for row in results)
    print(f"Integration readiness written: {md_path}")
    print(f"Integration readiness latest: {OUTPUT_DIR / 'integration_readiness_latest.md'}")
    print(f"Tool payload written: {json_path}")
    print("Status: BLOCKED" if blocked else "Status: READY")
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
