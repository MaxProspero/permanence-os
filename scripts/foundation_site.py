#!/usr/bin/env python3
"""
Serve the FOUNDATION landing page locally for live preview.
"""

from __future__ import annotations

import argparse
import os
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_SITE_DIR = os.path.join(BASE_DIR, "site", "foundation")


def _open_browser(url: str, delay_seconds: float = 1.0) -> None:
    time.sleep(delay_seconds)
    webbrowser.open(url)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve FOUNDATION landing page locally.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8787, help="Bind port")
    parser.add_argument("--site-dir", default=DEFAULT_SITE_DIR, help="Directory containing index.html")
    parser.add_argument("--no-open", action="store_true", help="Do not auto-open browser")
    args = parser.parse_args()

    site_dir = os.path.abspath(os.path.expanduser(args.site_dir))
    index_path = os.path.join(site_dir, "index.html")
    if not os.path.exists(index_path):
        print(f"Missing site entrypoint: {index_path}")
        return 2

    handler = lambda *handler_args, **handler_kwargs: SimpleHTTPRequestHandler(  # noqa: E731
        *handler_args,
        directory=site_dir,
        **handler_kwargs,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"

    if not args.no_open:
        thread = threading.Thread(target=_open_browser, args=(url,), daemon=True)
        thread.start()

    print(f"Serving FOUNDATION site: {site_dir}")
    print(f"URL: {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
