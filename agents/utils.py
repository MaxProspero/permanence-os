#!/usr/bin/env python3
"""
Shared utilities for agents.
"""

import os
from datetime import datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.getenv("PERMANENCE_LOG_DIR", os.path.join(BASE_DIR, "logs"))


def log(message: str, level: str = "INFO") -> str:
    """Append-only log entry for all agents."""
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"[{timestamp}] [{level}] {message}"

    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log")
    with open(log_file, "a") as f:
        f.write(entry + "\n")

    print(entry)
    return entry
