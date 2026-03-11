#!/usr/bin/env python3
"""Security-focused tests for OpenClaw status capture."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.openclaw_status import capture_openclaw_status  # noqa: E402


def test_openclaw_status_redacts_output_and_strips_unrelated_env() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cli_path = root / "openclaw"
        cli_path.write_text(
            "#!/bin/sh\n"
            "if [ -n \"${ANTHROPIC_API_KEY:-}\" ]; then echo 'anthropic_env_present=yes'; else echo 'anthropic_env_present=no'; fi\n"
            "echo 'token=sk-test-secret-value'\n"
            "echo 'url=https://example.test?api_key=secret123&mode=1'\n"
            "echo 'Authorization: Bearer ghp_test_secret_value' 1>&2\n",
            encoding="utf-8",
        )
        cli_path.chmod(0o755)

        snapshot = {key: os.environ.get(key) for key in ("OPENCLAW_CLI", "PERMANENCE_TOOL_DIR", "ANTHROPIC_API_KEY")}
        try:
            os.environ["OPENCLAW_CLI"] = str(cli_path)
            os.environ["PERMANENCE_TOOL_DIR"] = str(root / "tool")
            os.environ["ANTHROPIC_API_KEY"] = "live-secret-should-not-reach-openclaw"
            output_path = root / "openclaw_status.txt"
            result = capture_openclaw_status(output=str(output_path))
            assert result.get("status") == "ok"

            payload = output_path.read_text(encoding="utf-8")
            assert "anthropic_env_present=no" in payload
            assert "live-secret-should-not-reach-openclaw" not in payload
            assert "sk-test-secret-value" not in payload
            assert "secret123" not in payload
            assert "ghp_test_secret_value" not in payload
            assert "[REDACTED]" in payload or "[REDACTED_SECRET]" in payload
        finally:
            for key, value in snapshot.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
