#!/usr/bin/env python3
"""Tests for Anthropic keychain helper."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.anthropic_keychain as key_mod  # noqa: E402


def test_anthropic_keychain_install_updates_env_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        env_path = root / ".env"
        env_path.write_text("ANTHROPIC_API_KEY=old\nOPENAI_API_KEY=test\n", encoding="utf-8")
        key_path = root / "anthropic.key"
        key_path.write_text("sk-ant-test-secret\n", encoding="utf-8")

        original = {
            "BASE_DIR": key_mod.BASE_DIR,
            "_set_keychain": key_mod._set_keychain,
        }
        try:
            key_mod.BASE_DIR = root
            key_mod._set_keychain = lambda service, account, key: True  # type: ignore[assignment]
            rc = key_mod.main(
                [
                    "--from-file",
                    str(key_path),
                    "--service",
                    "svc.test",
                    "--account",
                    "acct.test",
                ]
            )
        finally:
            key_mod.BASE_DIR = original["BASE_DIR"]
            key_mod._set_keychain = original["_set_keychain"]

        assert rc == 0
        text = env_path.read_text(encoding="utf-8")
        assert "ANTHROPIC_API_KEY=\n" in text
        assert "PERMANENCE_ANTHROPIC_KEYCHAIN_SERVICE=svc.test" in text
        assert "PERMANENCE_ANTHROPIC_KEYCHAIN_ACCOUNT=acct.test" in text


def test_anthropic_keychain_rejects_bad_format():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        key_path = root / "anthropic.key"
        key_path.write_text("not-a-real-key\n", encoding="utf-8")

        original = {"BASE_DIR": key_mod.BASE_DIR}
        try:
            key_mod.BASE_DIR = root
            rc = key_mod.main(["--from-file", str(key_path)])
        finally:
            key_mod.BASE_DIR = original["BASE_DIR"]

        assert rc == 1


if __name__ == "__main__":
    test_anthropic_keychain_install_updates_env_file()
    test_anthropic_keychain_rejects_bad_format()
    print("✓ Anthropic keychain tests passed")
