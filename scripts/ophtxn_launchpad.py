#!/usr/bin/env python3
"""
Ophtxn official launch readiness checks and launch planning.
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

SURFACE_FILES = [
    ("Official landing", BASE_DIR / "site" / "foundation" / "index.html"),
    ("Official app studio", BASE_DIR / "site" / "foundation" / "official_app.html"),
    ("Press kit", BASE_DIR / "site" / "foundation" / "press_kit.html"),
    ("Logo mark", BASE_DIR / "site" / "foundation" / "assets" / "ophtxn_mark.svg"),
]
DOC_FILES = [
    ("Operator command guide", BASE_DIR / "docs" / "ophtxn_operator_command_guide.md"),
    ("Official launch path", BASE_DIR / "docs" / "ophtxn_official_launch_path_20260305.md"),
    ("Venture radar", BASE_DIR / "docs" / "ophtxn_venture_radar_20260305.md"),
]
REQUIRED_ROUTE_TOKENS = ("/app/official", "/app/studio", "/app/press")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat().replace("+00:00", "Z")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _score(passed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((max(0, passed) / total) * 100.0, 1)


def _keychain_secret(service: str, account: str) -> str:
    if sys.platform != "darwin":
        return ""
    if not service or not account:
        return ""
    proc = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return str(proc.stdout or "").strip()


def _secret_present(*, env_key: str, service_key: str, account_key: str, default_service: str) -> bool:
    raw = str(os.getenv(env_key, "")).strip()
    if raw:
        return True
    service = str(os.getenv(service_key, default_service)).strip()
    account = str(os.getenv(account_key, os.getenv("USER", ""))).strip()
    return bool(_keychain_secret(service=service, account=account))


def _route_checks() -> list[dict[str, Any]]:
    server_file = BASE_DIR / "app" / "foundation" / "server.py"
    if not server_file.exists():
        return [{"route": token, "ok": False} for token in REQUIRED_ROUTE_TOKENS]
    text = server_file.read_text(encoding="utf-8", errors="ignore")
    out: list[dict[str, Any]] = []
    for token in REQUIRED_ROUTE_TOKENS:
        out.append({"route": token, "ok": token in text})
    return out


def _file_checks(rows: list[tuple[str, Path]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for label, path in rows:
        out.append({"label": label, "path": str(path), "ok": path.exists()})
    return out


def _connector_checks() -> list[dict[str, Any]]:
    telegram_token_ok = _secret_present(
        env_key="PERMANENCE_TELEGRAM_BOT_TOKEN",
        service_key="PERMANENCE_TELEGRAM_BOT_TOKEN_KEYCHAIN_SERVICE",
        account_key="PERMANENCE_TELEGRAM_BOT_TOKEN_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_telegram_bot_token",
    )
    discord_token_ok = _secret_present(
        env_key="PERMANENCE_DISCORD_BOT_TOKEN",
        service_key="PERMANENCE_DISCORD_BOT_TOKEN_KEYCHAIN_SERVICE",
        account_key="PERMANENCE_DISCORD_BOT_TOKEN_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_discord_bot_token",
    )
    x_token_ok = _secret_present(
        env_key="PERMANENCE_SOCIAL_READ_TOKEN",
        service_key="PERMANENCE_SOCIAL_READ_KEYCHAIN_SERVICE",
        account_key="PERMANENCE_SOCIAL_READ_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_social_read_token",
    )

    chat_id = str(os.getenv("PERMANENCE_TELEGRAM_CHAT_ID", "")).strip()
    chat_ids = str(os.getenv("PERMANENCE_TELEGRAM_CHAT_IDS", "")).strip()
    telegram_chat_ok = bool(chat_id or chat_ids)
    discord_channel_ok = bool(
        str(os.getenv("PERMANENCE_DISCORD_DEFAULT_CHANNEL_ID", "")).strip()
        or str(os.getenv("PERMANENCE_DISCORD_CHANNEL_ID", "")).strip()
    )

    return [
        {"label": "Telegram bot token", "ok": telegram_token_ok, "required": True},
        {"label": "Telegram chat target", "ok": telegram_chat_ok, "required": True},
        {"label": "Discord bot token", "ok": discord_token_ok, "required": True},
        {"label": "Discord default channel", "ok": discord_channel_ok, "required": False},
        {"label": "X read token (research ingest)", "ok": x_token_ok, "required": False},
    ]


def _ops_checks() -> list[dict[str, Any]]:
    no_spend = _is_true(os.getenv("PERMANENCE_NO_SPEND_MODE", "0"))
    low_cost = _is_true(os.getenv("PERMANENCE_LOW_COST_MODE", "0"))
    provider = str(os.getenv("PERMANENCE_MODEL_PROVIDER", "anthropic")).strip().lower() or "anthropic"
    caps = str(os.getenv("PERMANENCE_MODEL_PROVIDER_CAPS_USD", "")).strip()
    return [
        {"label": "No-spend mode enabled", "ok": no_spend, "value": no_spend},
        {"label": "Low-cost mode enabled", "ok": low_cost, "value": low_cost},
        {"label": "Provider is ollama", "ok": provider == "ollama", "value": provider},
        {"label": "Provider caps configured", "ok": bool(caps), "value": caps or "-"},
    ]


def _next_ten(
    *,
    surface_checks: list[dict[str, Any]],
    route_checks: list[dict[str, Any]],
    doc_checks: list[dict[str, Any]],
    connector_checks: list[dict[str, Any]],
    ops_checks: list[dict[str, Any]],
) -> list[str]:
    steps: list[str] = []

    for row in surface_checks:
        if not bool(row.get("ok")):
            label = str(row.get("label") or "surface asset")
            path = str(row.get("path") or "")
            steps.append(f"Restore missing {label} at {path}.")
    for row in route_checks:
        if not bool(row.get("ok")):
            steps.append(f"Add missing foundation API route {row.get('route')} in app/foundation/server.py.")
    for row in doc_checks:
        if not bool(row.get("ok")):
            label = str(row.get("label") or "launch doc")
            steps.append(f"Create or restore {label} documentation.")
    for row in connector_checks:
        if bool(row.get("required")) and (not bool(row.get("ok"))):
            steps.append(f"Configure required connector: {row.get('label')}.")
    for row in ops_checks:
        if not bool(row.get("ok")):
            label = str(row.get("label") or "ops guardrail")
            steps.append(f"Fix ops guardrail: {label}.")

    defaults = [
        "Run `python cli.py ophtxn-launchpad --action status --strict` before each release candidate.",
        "Run `python cli.py foundation-api` and verify /app/official, /app/studio, /app/press load cleanly.",
        "Publish a one-minute product demo from the App Studio flow.",
        "Post one weekly Operator Notes update summarizing shipped changes and user outcomes.",
        "Run `python cli.py ophtxn-production --action status --strict --min-score 80` before production deploy.",
        "Route all new idea links through `/idea-intake` then `/idea-run queue=1` for governed prioritization.",
        "Review `/platform-watch strict` at least twice weekly to catch API drift before breakage.",
        "Keep Telegram + Discord command surface synchronized with `docs/ophtxn_operator_command_guide.md`.",
        "Define one paid starter offer and connect it to sales pipeline intake.",
        "Track launch KPIs weekly: leads, paid conversions, and avg response time.",
        "Open a weekly release branch and ship small updates instead of large batch drops.",
    ]

    for row in defaults:
        if len(steps) >= 10:
            break
        steps.append(row)
    return steps[:10]


def _build_plan(next_ten: list[str]) -> list[str]:
    lines = [
        "## 0-30 Days",
        "- Lock personal runtime quality: no-spend on, daily ops loop stable, approvals queue under control.",
        "- Use App Studio + press assets to standardize external demos and onboarding.",
        "- Publish weekly Operator Notes from real system outputs.",
        "",
        "## 30-60 Days",
        "- Ship one clear paid offer with strict delivery boundaries.",
        "- Run outbound/inbound experiments and track conversion by source.",
        "- Keep integrations read-first and governance-gated.",
        "",
        "## 60-90 Days",
        "- Productize best-performing workflow as a reusable pack.",
        "- Add stronger onboarding defaults and feedback loops.",
        "- Prepare multi-user architecture decisions for business mode.",
        "",
        "## Immediate Next 10",
    ]
    for idx, item in enumerate(next_ten, start=1):
        lines.append(f"{idx}. {item}")
    return lines


def _write_outputs(
    *,
    action: str,
    scores: dict[str, float],
    surface_checks: list[dict[str, Any]],
    route_checks: list[dict[str, Any]],
    doc_checks: list[dict[str, Any]],
    connector_checks: list[dict[str, Any]],
    ops_checks: list[dict[str, Any]],
    next_ten: list[str],
    output_override: Path | None,
) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = output_override if output_override else OUTPUT_DIR / f"ophtxn_launchpad_{stamp}.md"
    latest_md = OUTPUT_DIR / "ophtxn_launchpad_latest.md"
    json_path = TOOL_DIR / f"ophtxn_launchpad_{stamp}.json"

    lines: list[str] = [
        "# Ophtxn Launchpad",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Action: {action}",
        "",
        "## Readiness Scores",
        f"- Surface score: {scores.get('surface', 0.0):g}",
        f"- Documentation score: {scores.get('docs', 0.0):g}",
        f"- Connectors score: {scores.get('connectors', 0.0):g}",
        f"- Ops score: {scores.get('ops', 0.0):g}",
        f"- Overall score: {scores.get('overall', 0.0):g}",
        "",
        "## Surface Checks",
    ]
    for row in surface_checks:
        lines.append(f"- {row.get('label')}: ok={row.get('ok')} ({row.get('path')})")

    lines.append("")
    lines.append("## Foundation API Routes")
    for row in route_checks:
        lines.append(f"- {row.get('route')}: ok={row.get('ok')}")

    lines.append("")
    lines.append("## Documentation Checks")
    for row in doc_checks:
        lines.append(f"- {row.get('label')}: ok={row.get('ok')} ({row.get('path')})")

    lines.append("")
    lines.append("## Connector Readiness")
    for row in connector_checks:
        requirement = "required" if bool(row.get("required")) else "optional"
        lines.append(f"- {row.get('label')}: ok={row.get('ok')} ({requirement})")

    lines.append("")
    lines.append("## Ops Guardrails")
    for row in ops_checks:
        lines.append(f"- {row.get('label')}: ok={row.get('ok')} (value={row.get('value')})")

    lines.append("")
    lines.append("## Launch Next 10")
    for idx, item in enumerate(next_ten, start=1):
        lines.append(f"{idx}. {item}")

    lines.extend(
        [
            "",
            "## Command Shortcuts",
            "- `python cli.py ophtxn-launchpad --action status`",
            "- `python cli.py ophtxn-launchpad --action status --strict --min-score 80`",
            "- `python cli.py ophtxn-launchpad --action plan`",
            "- Telegram: `/launch-status`, `/launch-plan`",
            "",
        ]
    )

    if action == "plan":
        lines.extend(_build_plan(next_ten))
        lines.append("")

    markdown = "\n".join(lines)
    md_path.write_text(markdown + "\n", encoding="utf-8")
    latest_md.write_text(markdown + "\n", encoding="utf-8")

    payload = {
        "generated_at": _now_iso(),
        "action": action,
        "scores": scores,
        "surface_checks": surface_checks,
        "route_checks": route_checks,
        "doc_checks": doc_checks,
        "connector_checks": connector_checks,
        "ops_checks": ops_checks,
        "next_ten": next_ten,
        "latest_markdown": str(latest_md),
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Ophtxn launch readiness + plan outputs.")
    parser.add_argument("--action", choices=["status", "plan"], default="status", help="Launchpad action")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when overall score is below min-score")
    parser.add_argument("--min-score", type=float, default=75.0, help="Strict minimum overall score")
    parser.add_argument("--output", help="Optional markdown output path")
    args = parser.parse_args(argv)

    surface_checks = _file_checks(SURFACE_FILES)
    route_checks = _route_checks()
    doc_checks = _file_checks(DOC_FILES)
    connector_checks = _connector_checks()
    ops_checks = _ops_checks()

    surface_score = _score(
        passed=sum(1 for row in surface_checks if bool(row.get("ok"))) + sum(1 for row in route_checks if bool(row.get("ok"))),
        total=len(surface_checks) + len(route_checks),
    )
    docs_score = _score(sum(1 for row in doc_checks if bool(row.get("ok"))), len(doc_checks))

    required_connector_rows = [row for row in connector_checks if bool(row.get("required"))]
    optional_connector_rows = [row for row in connector_checks if not bool(row.get("required"))]
    required_connector_score = _score(
        sum(1 for row in required_connector_rows if bool(row.get("ok"))),
        len(required_connector_rows),
    )
    optional_connector_score = _score(
        sum(1 for row in optional_connector_rows if bool(row.get("ok"))),
        len(optional_connector_rows),
    )
    connectors_score = round((required_connector_score * 0.85) + (optional_connector_score * 0.15), 1)

    ops_score = _score(sum(1 for row in ops_checks if bool(row.get("ok"))), len(ops_checks))

    overall = round((surface_score * 0.35) + (docs_score * 0.15) + (connectors_score * 0.25) + (ops_score * 0.25), 1)
    scores = {
        "surface": surface_score,
        "docs": docs_score,
        "connectors": connectors_score,
        "ops": ops_score,
        "overall": overall,
    }

    next_ten = _next_ten(
        surface_checks=surface_checks,
        route_checks=route_checks,
        doc_checks=doc_checks,
        connector_checks=connector_checks,
        ops_checks=ops_checks,
    )

    output_override = Path(args.output).expanduser() if args.output else None
    md_path, json_path = _write_outputs(
        action=args.action,
        scores=scores,
        surface_checks=surface_checks,
        route_checks=route_checks,
        doc_checks=doc_checks,
        connector_checks=connector_checks,
        ops_checks=ops_checks,
        next_ten=next_ten,
        output_override=output_override,
    )

    print(f"[ophtxn-launchpad] action={args.action} overall={overall:g} markdown={md_path} json={json_path}")
    if args.strict and overall < max(0.0, min(100.0, _safe_float(args.min_score, 75.0))):
        print(f"[ophtxn-launchpad] strict gate failed: overall {overall:g} < min-score {args.min_score:g}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
