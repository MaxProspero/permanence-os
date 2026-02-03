#!/usr/bin/env python3
"""
Episodic Memory System for Permanence OS.
Append-only JSONL entries (parallel to per-task JSON state files).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class EpisodicMemory:
    """Append-only episodic memory for task records."""

    def __init__(self, memory_dir: Optional[str] = None):
        base_dir = memory_dir or os.getenv("PERMANENCE_MEMORY_DIR", "./memory")
        self.memory_dir = Path(base_dir) / "episodic"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def generate_task_id(self) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        suffix = hashlib.sha256(str(datetime.now(timezone.utc).timestamp()).encode()).hexdigest()[:8]
        return f"task_{ts}_{suffix}"

    def write_entry(self, entry: Dict[str, Any]) -> str:
        task_id = entry.get("task_id") or self.generate_task_id()
        entry["task_id"] = task_id
        entry["written_at"] = datetime.now(timezone.utc).isoformat()

        required = ["task_id", "timestamp", "risk_tier", "canon_checks", "governance"]
        for field in required:
            if field not in entry:
                raise ValueError(f"Episodic entry missing required field: {field}")

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.memory_dir / f"episodic_{date_str}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        return str(log_file)

    def read_entries(self, date: Optional[str] = None, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        pattern = f"episodic_{date}.jsonl" if date else "episodic_*.jsonl"
        for log_file in self.memory_dir.glob(pattern):
            with open(log_file, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue
                    if task_id and entry.get("task_id") != task_id:
                        continue
                    entries.append(entry)
        return entries


_memory: Optional[EpisodicMemory] = None


def get_episodic_memory() -> EpisodicMemory:
    global _memory
    if _memory is None:
        _memory = EpisodicMemory()
    return _memory


def log_task_episode(
    task_id: str,
    risk_tier: str,
    canon_checks: Dict[str, Any],
    governance: Dict[str, Any],
    tool_state: Dict[str, Any],
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    agents_involved: List[str],
    duration_seconds: float,
    identity_used: str = "kael_dax",
) -> str:
    entry = {
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "risk_tier": risk_tier,
        "canon_checks": canon_checks,
        "governance": governance,
        "tool_state": tool_state,
        "inputs": inputs,
        "outputs": outputs,
        "agents_involved": agents_involved,
        "duration_seconds": duration_seconds,
        "identity_used": identity_used,
    }
    return get_episodic_memory().write_entry(entry)
