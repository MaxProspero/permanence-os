#!/usr/bin/env python3
"""Tests for CLI keychain env injection."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cli as cli_mod  # noqa: E402


def test_inject_keychain_env_sets_multiple_tokens():
    env = {
        "PERMANENCE_ANTHROPIC_KEYCHAIN_SERVICE": "svc.anthropic",
        "PERMANENCE_ANTHROPIC_KEYCHAIN_ACCOUNT": "acct.anthropic",
        "OPENAI_KEYCHAIN_SERVICE": "svc.openai",
        "OPENAI_KEYCHAIN_ACCOUNT": "acct.openai",
        "PERMANENCE_GITHUB_READ_KEYCHAIN_SERVICE": "svc.github",
        "PERMANENCE_GITHUB_READ_KEYCHAIN_ACCOUNT": "acct.github",
        "PERMANENCE_SOCIAL_READ_KEYCHAIN_SERVICE": "svc.social",
        "PERMANENCE_SOCIAL_READ_KEYCHAIN_ACCOUNT": "acct.social",
        "PERMANENCE_DISCORD_ALERT_WEBHOOK_KEYCHAIN_SERVICE": "svc.discord",
        "PERMANENCE_DISCORD_ALERT_WEBHOOK_KEYCHAIN_ACCOUNT": "acct.discord",
        "PERMANENCE_DISCORD_BOT_TOKEN_KEYCHAIN_SERVICE": "svc.discord.bot",
        "PERMANENCE_DISCORD_BOT_TOKEN_KEYCHAIN_ACCOUNT": "acct.discord.bot",
        "PERMANENCE_TELEGRAM_BOT_TOKEN_KEYCHAIN_SERVICE": "svc.telegram",
        "PERMANENCE_TELEGRAM_BOT_TOKEN_KEYCHAIN_ACCOUNT": "acct.telegram",
        "XAI_KEYCHAIN_SERVICE": "svc.xai",
        "XAI_KEYCHAIN_ACCOUNT": "acct.xai",
        "ALPHA_VANTAGE_KEYCHAIN_SERVICE": "svc.alpha",
        "ALPHA_VANTAGE_KEYCHAIN_ACCOUNT": "acct.alpha",
        "FINNHUB_KEYCHAIN_SERVICE": "svc.finnhub",
        "FINNHUB_KEYCHAIN_ACCOUNT": "acct.finnhub",
        "POLYGON_KEYCHAIN_SERVICE": "svc.polygon",
        "POLYGON_KEYCHAIN_ACCOUNT": "acct.polygon",
        "COINMARKETCAP_KEYCHAIN_SERVICE": "svc.cmc",
        "COINMARKETCAP_KEYCHAIN_ACCOUNT": "acct.cmc",
        "GLASSNODE_KEYCHAIN_SERVICE": "svc.glassnode",
        "GLASSNODE_KEYCHAIN_ACCOUNT": "acct.glassnode",
    }

    def fake_keychain_secret(service: str, account: str) -> str:
        mapping = {
            ("svc.anthropic", "acct.anthropic"): "sk-ant-test-value",
            ("svc.openai", "acct.openai"): "sk-openai-test-value",
            ("svc.github", "acct.github"): "gh_read_token_abcdefghijklmnopqrstuvwxyz123456",
            ("svc.social", "acct.social"): "social_read_token_value_123456",
            ("svc.discord", "acct.discord"): "https://discord.com/api/webhooks/123/abc",
            ("svc.discord.bot", "acct.discord.bot"): "discord_bot_token_value_abcdefghijklmnopqrstuvwxyz_123456",
            ("svc.telegram", "acct.telegram"): "123456:telegram_bot_token_value_abcdefghijklmnopqrstuvwxyz",
            ("svc.xai", "acct.xai"): "xai-test-key-abcdefghijklmnopqrstuvwxyz123456",
            ("svc.alpha", "acct.alpha"): "ALPHAKEY123456",
            ("svc.finnhub", "acct.finnhub"): "FINNHUBKEY123456",
            ("svc.polygon", "acct.polygon"): "POLYGONKEY123456",
            ("svc.cmc", "acct.cmc"): "COINMARKETCAPKEY123456",
            ("svc.glassnode", "acct.glassnode"): "GLASSNODEKEY123456",
        }
        return mapping.get((service, account), "")

    original = cli_mod._keychain_secret
    try:
        cli_mod._keychain_secret = fake_keychain_secret  # type: ignore[assignment]
        cli_mod._inject_keychain_env(env)
    finally:
        cli_mod._keychain_secret = original

    assert env.get("ANTHROPIC_API_KEY") == "sk-ant-test-value"
    assert env.get("OPENAI_API_KEY") == "sk-openai-test-value"
    assert env.get("PERMANENCE_GITHUB_READ_TOKEN", "").startswith("gh_read_token_")
    assert env.get("PERMANENCE_SOCIAL_READ_TOKEN", "").startswith("social_read_token_value_")
    assert env.get("PERMANENCE_DISCORD_ALERT_WEBHOOK_URL", "").startswith("https://discord.com/api/webhooks/")
    assert env.get("PERMANENCE_DISCORD_BOT_TOKEN", "").startswith("discord_bot_token_value_")
    assert env.get("PERMANENCE_TELEGRAM_BOT_TOKEN", "").startswith("123456:telegram_bot_token_value_")
    assert env.get("XAI_API_KEY", "").startswith("xai-test-key-")
    assert env.get("ALPHA_VANTAGE_API_KEY") == "ALPHAKEY123456"
    assert env.get("FINNHUB_API_KEY") == "FINNHUBKEY123456"
    assert env.get("POLYGON_API_KEY") == "POLYGONKEY123456"
    assert env.get("COINMARKETCAP_API_KEY") == "COINMARKETCAPKEY123456"
    assert env.get("GLASSNODE_API_KEY") == "GLASSNODEKEY123456"


if __name__ == "__main__":
    test_inject_keychain_env_sets_multiple_tokens()
    print("✓ CLI keychain injection tests passed")
