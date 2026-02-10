#!/usr/bin/env python3
"""
Run Interface Agent intake listener.
"""

from __future__ import annotations

import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from core.interface_agent import InterfaceAgent  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Interface Agent server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--max-payload-bytes", type=int, default=64_000, help="Payload cap")
    args = parser.parse_args()

    agent = InterfaceAgent(max_payload_bytes=args.max_payload_bytes)
    agent.listen(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
