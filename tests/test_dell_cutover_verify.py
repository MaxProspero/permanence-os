#!/usr/bin/env python3
"""Tests for Dell cutover verification helpers."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.dell_cutover_verify import cron_slots_present, extract_managed_cron_block, load_env_keys  # noqa: E402


def test_extract_managed_cron_block_and_slots():
    text = """
MAILTO=""
# >>> permanence-automation >>>
0 7 * * * cd /repo && /usr/bin/env bash automation/run_briefing.sh >> /repo/logs/automation/cron.log 2>&1
0 12 * * * cd /repo && /usr/bin/env bash automation/run_briefing.sh >> /repo/logs/automation/cron.log 2>&1
0 19 * * * cd /repo && /usr/bin/env bash automation/run_briefing.sh >> /repo/logs/automation/cron.log 2>&1
# <<< permanence-automation <<<
"""
    block = extract_managed_cron_block(text)
    assert len(block) == 3
    assert cron_slots_present(block) is True


def test_load_env_keys_reads_required_values():
    with tempfile.TemporaryDirectory() as temp:
        env_path = Path(temp) / ".env"
        env_path.write_text(
            "PERMANENCE_STORAGE_ROOT=/Volumes/LaCie\n"
            "PERMANENCE_NOTEBOOKLM_SYNC=1\n"
        )
        keys = load_env_keys(env_path)
        assert "PERMANENCE_STORAGE_ROOT" in keys
        assert "PERMANENCE_NOTEBOOKLM_SYNC" in keys


if __name__ == "__main__":
    test_extract_managed_cron_block_and_slots()
    test_load_env_keys_reads_required_values()
    print("ok")
