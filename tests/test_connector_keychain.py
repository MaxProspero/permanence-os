#!/usr/bin/env python3
"""Tests for connector keychain helper."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.connector_keychain as mod  # noqa: E402


def test_connector_keychain_install_updates_env():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_path = root / ".env"
        env_path.write_text("PERMANENCE_GITHUB_READ_TOKEN=old\n", encoding="utf-8")
        token_path = root / "github.token"
        token_path.write_text("gh_read_token_abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8")

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "_set_keychain": mod._set_keychain,
        }
        try:
            mod.BASE_DIR = root
            mod._set_keychain = lambda service, account, secret: True  # type: ignore[assignment]
            rc = mod.main(
                [
                    "--target",
                    "github-read",
                    "--from-file",
                    str(token_path),
                    "--service",
                    "svc.github.read",
                    "--account",
                    "acct.github.read",
                ]
            )
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod._set_keychain = original["_set_keychain"]

        assert rc == 0
        text = env_path.read_text(encoding="utf-8")
        assert "PERMANENCE_GITHUB_READ_TOKEN=\n" in text
        assert "PERMANENCE_GITHUB_READ_KEYCHAIN_SERVICE=svc.github.read" in text
        assert "PERMANENCE_GITHUB_READ_KEYCHAIN_ACCOUNT=acct.github.read" in text


def test_connector_keychain_rejects_invalid_social_token():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        token_path = root / "social.token"
        token_path.write_text("short\n", encoding="utf-8")

        original = {"BASE_DIR": mod.BASE_DIR}
        try:
            mod.BASE_DIR = root
            rc = mod.main(["--target", "social-read", "--from-file", str(token_path)])
        finally:
            mod.BASE_DIR = original["BASE_DIR"]

        assert rc == 1


def test_connector_keychain_installs_discord_webhook():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_path = root / ".env"
        env_path.write_text("", encoding="utf-8")
        token_path = root / "discord_webhook.txt"
        token_path.write_text("https://discord.com/api/webhooks/1234567890/abcdefg\n", encoding="utf-8")

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "_set_keychain": mod._set_keychain,
        }
        try:
            mod.BASE_DIR = root
            mod._set_keychain = lambda service, account, secret: True  # type: ignore[assignment]
            rc = mod.main(
                [
                    "--target",
                    "discord-alert-webhook",
                    "--from-file",
                    str(token_path),
                    "--service",
                    "svc.discord",
                    "--account",
                    "acct.discord",
                ]
            )
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod._set_keychain = original["_set_keychain"]

        assert rc == 0
        text = env_path.read_text(encoding="utf-8")
        assert "PERMANENCE_DISCORD_ALERT_WEBHOOK_URL=\n" in text
        assert "PERMANENCE_DISCORD_ALERT_WEBHOOK_KEYCHAIN_SERVICE=svc.discord" in text
        assert "PERMANENCE_DISCORD_ALERT_WEBHOOK_KEYCHAIN_ACCOUNT=acct.discord" in text


def test_connector_keychain_installs_discord_bot_token():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_path = root / ".env"
        env_path.write_text("", encoding="utf-8")
        token_path = root / "discord_bot.token"
        token_path.write_text("discord_bot_token_value_abcdefghijklmnopqrstuvwxyz_123456\n", encoding="utf-8")

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "_set_keychain": mod._set_keychain,
        }
        try:
            mod.BASE_DIR = root
            mod._set_keychain = lambda service, account, secret: True  # type: ignore[assignment]
            rc = mod.main(
                [
                    "--target",
                    "discord-bot-token",
                    "--from-file",
                    str(token_path),
                    "--service",
                    "svc.discord.bot",
                    "--account",
                    "acct.discord.bot",
                ]
            )
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod._set_keychain = original["_set_keychain"]

        assert rc == 0
        text = env_path.read_text(encoding="utf-8")
        assert "PERMANENCE_DISCORD_BOT_TOKEN=\n" in text
        assert "PERMANENCE_DISCORD_BOT_TOKEN_KEYCHAIN_SERVICE=svc.discord.bot" in text
        assert "PERMANENCE_DISCORD_BOT_TOKEN_KEYCHAIN_ACCOUNT=acct.discord.bot" in text


def test_connector_keychain_installs_market_api_key():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_path = root / ".env"
        env_path.write_text("", encoding="utf-8")
        token_path = root / "alpha_vantage.key"
        token_path.write_text("ALPHAVANTAGEKEY123456\n", encoding="utf-8")

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "_set_keychain": mod._set_keychain,
        }
        try:
            mod.BASE_DIR = root
            mod._set_keychain = lambda service, account, secret: True  # type: ignore[assignment]
            rc = mod.main(
                [
                    "--target",
                    "alpha-vantage",
                    "--from-file",
                    str(token_path),
                    "--service",
                    "svc.alpha",
                    "--account",
                    "acct.alpha",
                ]
            )
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod._set_keychain = original["_set_keychain"]

        assert rc == 0
        text = env_path.read_text(encoding="utf-8")
        assert "ALPHA_VANTAGE_API_KEY=\n" in text
        assert "ALPHA_VANTAGE_KEYCHAIN_SERVICE=svc.alpha" in text
        assert "ALPHA_VANTAGE_KEYCHAIN_ACCOUNT=acct.alpha" in text


def test_connector_keychain_installs_xai_api_key():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_path = root / ".env"
        env_path.write_text("", encoding="utf-8")
        token_path = root / "xai.key"
        token_path.write_text("xai-test-key-abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8")

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "_set_keychain": mod._set_keychain,
        }
        try:
            mod.BASE_DIR = root
            mod._set_keychain = lambda service, account, secret: True  # type: ignore[assignment]
            rc = mod.main(
                [
                    "--target",
                    "xai-api-key",
                    "--from-file",
                    str(token_path),
                    "--service",
                    "svc.xai",
                    "--account",
                    "acct.xai",
                ]
            )
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod._set_keychain = original["_set_keychain"]

        assert rc == 0
        text = env_path.read_text(encoding="utf-8")
        assert "XAI_API_KEY=\n" in text
        assert "XAI_KEYCHAIN_SERVICE=svc.xai" in text
        assert "XAI_KEYCHAIN_ACCOUNT=acct.xai" in text


def test_connector_keychain_installs_openai_api_key():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_path = root / ".env"
        env_path.write_text("", encoding="utf-8")
        token_path = root / "openai.key"
        token_path.write_text("sk-openai-test-key-abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8")

        original = {
            "BASE_DIR": mod.BASE_DIR,
            "_set_keychain": mod._set_keychain,
        }
        try:
            mod.BASE_DIR = root
            mod._set_keychain = lambda service, account, secret: True  # type: ignore[assignment]
            rc = mod.main(
                [
                    "--target",
                    "openai-api-key",
                    "--from-file",
                    str(token_path),
                    "--service",
                    "svc.openai",
                    "--account",
                    "acct.openai",
                ]
            )
        finally:
            mod.BASE_DIR = original["BASE_DIR"]
            mod._set_keychain = original["_set_keychain"]

        assert rc == 0
        text = env_path.read_text(encoding="utf-8")
        assert "OPENAI_API_KEY=\n" in text
        assert "OPENAI_KEYCHAIN_SERVICE=svc.openai" in text
        assert "OPENAI_KEYCHAIN_ACCOUNT=acct.openai" in text


if __name__ == "__main__":
    test_connector_keychain_install_updates_env()
    test_connector_keychain_rejects_invalid_social_token()
    test_connector_keychain_installs_discord_webhook()
    test_connector_keychain_installs_discord_bot_token()
    test_connector_keychain_installs_market_api_key()
    test_connector_keychain_installs_xai_api_key()
    test_connector_keychain_installs_openai_api_key()
    print("✓ Connector keychain tests passed")
