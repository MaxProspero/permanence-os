#!/usr/bin/env python3
"""
Install or inspect Anthropic API key in macOS Keychain for safer local usage.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SERVICE = "permanence_os_anthropic_api_key"
DEFAULT_ACCOUNT = os.getenv("USER", "operator")

KEY_PATTERN = re.compile(r"^sk-ant-[A-Za-z0-9._\-]+$")


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _valid_key(value: str) -> bool:
    return bool(KEY_PATTERN.match(value.strip()))


def _run_security(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["security", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _set_keychain(service: str, account: str, key: str) -> bool:
    proc = _run_security(["add-generic-password", "-s", service, "-a", account, "-w", key, "-U"])
    return proc.returncode == 0


def _get_keychain(service: str, account: str) -> str:
    proc = _run_security(["find-generic-password", "-s", service, "-a", account, "-w"])
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _delete_keychain(service: str, account: str) -> bool:
    proc = _run_security(["delete-generic-password", "-s", service, "-a", account])
    return proc.returncode == 0


def _update_env(service: str, account: str) -> None:
    env_path = BASE_DIR / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    updates = {
        "ANTHROPIC_API_KEY": "",
        "PERMANENCE_ANTHROPIC_KEYCHAIN_SERVICE": service,
        "PERMANENCE_ANTHROPIC_KEYCHAIN_ACCOUNT": account,
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

    env_path.write_text("\n".join(merged).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage Anthropic key in macOS Keychain.")
    parser.add_argument("--from-file", help="Path to file containing only the Anthropic API key")
    parser.add_argument("--service", default=DEFAULT_SERVICE, help="Keychain service label")
    parser.add_argument("--account", default=DEFAULT_ACCOUNT, help="Keychain account label")
    parser.add_argument("--remove-source", action="store_true", help="Delete key source file after install")
    parser.add_argument("--status", action="store_true", help="Show whether key exists in keychain")
    parser.add_argument("--clear", action="store_true", help="Delete keychain entry for this service/account")
    args = parser.parse_args(argv)

    if os.uname().sysname.lower() != "darwin":
        print("This command currently supports macOS keychain only.")
        return 1

    service = str(args.service).strip() or DEFAULT_SERVICE
    account = str(args.account).strip() or DEFAULT_ACCOUNT

    if args.clear:
        deleted = _delete_keychain(service=service, account=account)
        _update_env(service=service, account=account)
        print(f"Keychain entry deleted: {'yes' if deleted else 'no'}")
        return 0 if deleted else 1

    if args.status:
        found = bool(_get_keychain(service=service, account=account))
        print(f"Keychain key present: {'yes' if found else 'no'}")
        print(f"service={service}")
        print(f"account={account}")
        return 0

    if not args.from_file:
        parser.error("--from-file is required unless using --status or --clear")

    source = Path(args.from_file).expanduser()
    if not source.exists():
        print(f"Key file not found: {source}")
        return 1

    key = _read_file(source)
    if not _valid_key(key):
        print("Invalid key format. Expected value starting with 'sk-ant-'.")
        return 1

    ok = _set_keychain(service=service, account=account, key=key)
    if not ok:
        print("Failed to write key to keychain.")
        return 1

    _update_env(service=service, account=account)
    if args.remove_source:
        try:
            source.unlink()
        except OSError:
            pass

    print("Anthropic key installed to keychain.")
    print(f"service={service}")
    print(f"account={account}")
    print("Updated .env to read key from keychain workflow (ANTHROPIC_API_KEY left blank).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
