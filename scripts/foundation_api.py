#!/usr/bin/env python3
"""
Run the FOUNDATION app API scaffold (auth + onboarding + memory schema/entries).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repository root is importable when launched as scripts/foundation_api.py.
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.foundation.server import create_app


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FOUNDATION API scaffold.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8797, help="Bind port")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=max(1, int(args.port)), debug=bool(args.debug))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
