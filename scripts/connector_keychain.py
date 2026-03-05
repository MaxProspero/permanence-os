#!/usr/bin/env python3
"""
Install/check/remove connector tokens in macOS Keychain.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ACCOUNT = os.getenv("USER", "operator")


@dataclass(frozen=True)
class Target:
    name: str
    env_key: str
    service_env: str
    account_env: str
    default_service: str
    help_text: str
    pattern: re.Pattern[str]


TARGETS = {
    "github-read": Target(
        name="github-read",
        env_key="PERMANENCE_GITHUB_READ_TOKEN",
        service_env="PERMANENCE_GITHUB_READ_KEYCHAIN_SERVICE",
        account_env="PERMANENCE_GITHUB_READ_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_github_read_token",
        help_text="GitHub read-only token (fine-grained PAT or app token).",
        pattern=re.compile(r"^(github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|[A-Za-z0-9._-]{20,})$"),
    ),
    "social-read": Target(
        name="social-read",
        env_key="PERMANENCE_SOCIAL_READ_TOKEN",
        service_env="PERMANENCE_SOCIAL_READ_KEYCHAIN_SERVICE",
        account_env="PERMANENCE_SOCIAL_READ_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_social_read_token",
        help_text="Read-only social platform token (X/other provider).",
        pattern=re.compile(r"^\S{16,}$"),
    ),
    "discord-alert-webhook": Target(
        name="discord-alert-webhook",
        env_key="PERMANENCE_DISCORD_ALERT_WEBHOOK_URL",
        service_env="PERMANENCE_DISCORD_ALERT_WEBHOOK_KEYCHAIN_SERVICE",
        account_env="PERMANENCE_DISCORD_ALERT_WEBHOOK_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_discord_alert_webhook",
        help_text="Discord webhook URL used for world-watch alert dispatch.",
        pattern=re.compile(r"^https://(?:discord(?:app)?\.com)/api/webhooks/\S+$"),
    ),
    "discord-bot-token": Target(
        name="discord-bot-token",
        env_key="PERMANENCE_DISCORD_BOT_TOKEN",
        service_env="PERMANENCE_DISCORD_BOT_TOKEN_KEYCHAIN_SERVICE",
        account_env="PERMANENCE_DISCORD_BOT_TOKEN_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_discord_bot_token",
        help_text="Discord bot token used for read-only server/channel research ingest.",
        pattern=re.compile(r"^\S{20,}$"),
    ),
    "telegram-bot-token": Target(
        name="telegram-bot-token",
        env_key="PERMANENCE_TELEGRAM_BOT_TOKEN",
        service_env="PERMANENCE_TELEGRAM_BOT_TOKEN_KEYCHAIN_SERVICE",
        account_env="PERMANENCE_TELEGRAM_BOT_TOKEN_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_telegram_bot_token",
        help_text="Telegram bot token used for world-watch alert dispatch.",
        pattern=re.compile(r"^\d{5,}:[A-Za-z0-9_-]{20,}$"),
    ),
    "xai-api-key": Target(
        name="xai-api-key",
        env_key="XAI_API_KEY",
        service_env="XAI_KEYCHAIN_SERVICE",
        account_env="XAI_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_xai_api_key",
        help_text="xAI API key used for Grok model/API access.",
        pattern=re.compile(r"^\S{8,}$"),
    ),
    "alpha-vantage": Target(
        name="alpha-vantage",
        env_key="ALPHA_VANTAGE_API_KEY",
        service_env="ALPHA_VANTAGE_KEYCHAIN_SERVICE",
        account_env="ALPHA_VANTAGE_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_alpha_vantage_api_key",
        help_text="Alpha Vantage API key for market data.",
        pattern=re.compile(r"^\S{8,}$"),
    ),
    "finnhub": Target(
        name="finnhub",
        env_key="FINNHUB_API_KEY",
        service_env="FINNHUB_KEYCHAIN_SERVICE",
        account_env="FINNHUB_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_finnhub_api_key",
        help_text="Finnhub API key for market data.",
        pattern=re.compile(r"^\S{8,}$"),
    ),
    "polygon": Target(
        name="polygon",
        env_key="POLYGON_API_KEY",
        service_env="POLYGON_KEYCHAIN_SERVICE",
        account_env="POLYGON_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_polygon_api_key",
        help_text="Polygon API key for market data.",
        pattern=re.compile(r"^\S{8,}$"),
    ),
    "coinmarketcap": Target(
        name="coinmarketcap",
        env_key="COINMARKETCAP_API_KEY",
        service_env="COINMARKETCAP_KEYCHAIN_SERVICE",
        account_env="COINMARKETCAP_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_coinmarketcap_api_key",
        help_text="CoinMarketCap API key for crypto market data.",
        pattern=re.compile(r"^\S{8,}$"),
    ),
    "glassnode": Target(
        name="glassnode",
        env_key="GLASSNODE_API_KEY",
        service_env="GLASSNODE_KEYCHAIN_SERVICE",
        account_env="GLASSNODE_KEYCHAIN_ACCOUNT",
        default_service="permanence_os_glassnode_api_key",
        help_text="Glassnode API key for on-chain market intelligence.",
        pattern=re.compile(r"^\S{8,}$"),
    ),
}


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _valid_token(value: str, target: Target) -> bool:
    return bool(target.pattern.match(value.strip()))


def _run_security(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["security", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _set_keychain(service: str, account: str, secret: str) -> bool:
    proc = _run_security(["add-generic-password", "-s", service, "-a", account, "-w", secret, "-U"])
    return proc.returncode == 0


def _get_keychain(service: str, account: str) -> str:
    proc = _run_security(["find-generic-password", "-s", service, "-a", account, "-w"])
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _delete_keychain(service: str, account: str) -> bool:
    proc = _run_security(["delete-generic-password", "-s", service, "-a", account])
    return proc.returncode == 0


def _resolve_target(name: str) -> Target:
    key = name.strip().lower()
    target = TARGETS.get(key)
    if target is None:
        raise ValueError(f"Unsupported target: {name}")
    return target


def _env_lines() -> list[str]:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return []
    return env_path.read_text(encoding="utf-8", errors="ignore").splitlines()


def _write_env(lines: list[str]) -> None:
    env_path = BASE_DIR / ".env"
    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _update_env(target: Target, service: str, account: str) -> None:
    lines = _env_lines()
    updates = {
        target.env_key: "",
        target.service_env: service,
        target.account_env: account,
    }
    seen: set[str] = set()
    merged: list[str] = []
    for raw in lines:
        if "=" in raw and not raw.lstrip().startswith("#"):
            key, _value = raw.split("=", 1)
            clean_key = key.strip()
            if clean_key in updates:
                merged.append(f"{clean_key}={updates[clean_key]}")
                seen.add(clean_key)
                continue
        merged.append(raw)
    for key, value in updates.items():
        if key not in seen:
            merged.append(f"{key}={value}")
    _write_env(merged)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage connector tokens in macOS Keychain.")
    parser.add_argument("--target", required=True, choices=sorted(TARGETS.keys()))
    parser.add_argument("--from-file", help="Path to file containing only the token")
    parser.add_argument("--service", help="Override keychain service label")
    parser.add_argument("--account", help="Override keychain account label")
    parser.add_argument("--remove-source", action="store_true", help="Delete source file after install")
    parser.add_argument("--status", action="store_true", help="Show token presence in keychain")
    parser.add_argument("--clear", action="store_true", help="Delete keychain entry")
    args = parser.parse_args(argv)

    if os.uname().sysname.lower() != "darwin":
        print("This command currently supports macOS keychain only.")
        return 1

    target = _resolve_target(args.target)
    service = str(args.service or target.default_service).strip() or target.default_service
    account = str(args.account or DEFAULT_ACCOUNT).strip() or DEFAULT_ACCOUNT

    if args.clear:
        deleted = _delete_keychain(service=service, account=account)
        _update_env(target=target, service=service, account=account)
        print(f"Target: {target.name}")
        print(f"Keychain entry deleted: {'yes' if deleted else 'no'}")
        return 0 if deleted else 1

    if args.status:
        found = bool(_get_keychain(service=service, account=account))
        print(f"Target: {target.name}")
        print(f"Keychain token present: {'yes' if found else 'no'}")
        print(f"service={service}")
        print(f"account={account}")
        return 0

    if not args.from_file:
        parser.error("--from-file is required unless using --status or --clear")

    source = Path(args.from_file).expanduser()
    if not source.exists():
        print(f"Token file not found: {source}")
        return 1

    secret = _read_file(source)
    if not _valid_token(secret, target):
        print(f"Invalid token format for target '{target.name}'. {target.help_text}")
        return 1

    ok = _set_keychain(service=service, account=account, secret=secret)
    if not ok:
        print("Failed to write token to keychain.")
        return 1

    _update_env(target=target, service=service, account=account)
    if args.remove_source:
        try:
            source.unlink()
        except OSError:
            pass

    print(f"{target.name} token installed to keychain.")
    print(f"service={service}")
    print(f"account={account}")
    print(f"Updated .env to keep {target.env_key}= blank and use keychain workflow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
