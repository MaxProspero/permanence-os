#!/usr/bin/env python3
"""
Ingest X/Twitter bookmarks and enrich for knowledge graph and idea intake.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

BASE_DIR = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env()
WORKING_DIR = Path(os.getenv("PERMANENCE_WORKING_DIR", str(BASE_DIR / "memory" / "working")))
OUTPUT_DIR = Path(os.getenv("PERMANENCE_OUTPUT_DIR", str(BASE_DIR / "outputs")))
TOOL_DIR = Path(os.getenv("PERMANENCE_TOOL_DIR", str(BASE_DIR / "memory" / "tool")))
INBOX_DIR = Path(os.getenv("PERMANENCE_INBOX_DIR", str(BASE_DIR / "memory" / "inbox")))
GRAPH_PATH = Path(os.getenv("PERMANENCE_KNOWLEDGE_GRAPH_PATH", str(BASE_DIR / "knowledge_graph" / "graph.json")))
STATE_DIR = WORKING_DIR / "x_bookmark_ingest"
STATE_PATH = STATE_DIR / "state.json"
BOOKMARK_INTAKE_PATH = INBOX_DIR / "bookmark_intake.jsonl"

X_BOOKMARKS_URL = "https://api.twitter.com/2/users/{user_id}/bookmarks"
X_TOKEN_ENV = "PERMANENCE_X_USER_TOKEN"
X_USER_ID_ENV = "PERMANENCE_X_USER_ID"
TIMEOUT_SECONDS = int(os.getenv("PERMANENCE_X_BOOKMARK_TIMEOUT", "10"))
MAX_BOOKMARKS_DEFAULT = int(os.getenv("PERMANENCE_X_MAX_BOOKMARKS", "100"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _bookmark_id(url: str) -> str:
    return "bookmark_" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Topic classification
# ---------------------------------------------------------------------------

_TOPIC_MAP: list[tuple[list[str], str]] = [
    (["agent", "agents", "agentic"], "agents"),
    (["saas", "startup", "founder"], "startup"),
    (["claude", "anthropic", "openai", "llm", "ai"], "ai"),
    (["finance", "trading", "market"], "finance"),
    (["architecture", "system design"], "architecture"),
    (["workflow", "automation"], "workflow"),
    (["brain", "neuroscience", "cognit"], "neuroscience"),
    (["code", "coding", "programming"], "coding"),
    (["product", "growth"], "product"),
    (["knowledge graph", "context"], "knowledge-graph"),
]


def _classify_topic(text: str) -> list[str]:
    """Return unique topic tags matched from text via keyword map."""
    lower = text.lower()
    tags: list[str] = []
    for keywords, tag in _TOPIC_MAP:
        for kw in keywords:
            if kw in lower:
                if tag not in tags:
                    tags.append(tag)
                break
    return tags


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

_HIGH_VALUE_BONUSES: dict[str, int] = {
    "agents": 3,
    "ai": 2,
    "startup": 3,
    "finance": 2,
}


def _score_bookmark(text: str, topic_tags: list[str]) -> int:
    """Simple relevance score from 0-10."""
    score = len(topic_tags) * 2
    for tag in topic_tags:
        score += _HIGH_VALUE_BONUSES.get(tag, 0)
    return min(score, 10)


# ---------------------------------------------------------------------------
# Fetching bookmarks from X API v2
# ---------------------------------------------------------------------------


def _fetch_bookmarks(
    user_id: str,
    token: str,
    max_bookmarks: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch bookmarks from X API v2. Returns (bookmarks, warnings)."""
    warnings: list[str] = []
    bookmarks: list[dict[str, Any]] = []
    url = X_BOOKMARKS_URL.format(user_id=user_id)
    headers = {"Authorization": f"Bearer {token}"}
    params: dict[str, Any] = {
        "tweet.fields": "created_at,author_id,text,entities,public_metrics",
        "expansions": "author_id",
        "max_results": min(100, max_bookmarks),
    }
    collected = 0
    next_token: str | None = None

    while collected < max_bookmarks:
        if next_token:
            params["pagination_token"] = next_token

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            warnings.append(f"X API request failed: {exc}")
            break

        if response.status_code == 401:
            warnings.append("X API returned 401 Unauthorized. Regenerate PERMANENCE_X_USER_TOKEN.")
            break
        if response.status_code == 403:
            warnings.append("X API returned 403 Forbidden. Verify app permissions and OAuth 2.0 user context.")
            break
        if response.status_code == 429:
            warnings.append("X API returned 429 Too Many Requests. Rate limit reached.")
            break

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            warnings.append(f"X API HTTP error: {exc}")
            break

        try:
            payload = response.json()
        except ValueError as exc:
            warnings.append(f"X API response JSON decode error: {exc}")
            break

        data = payload.get("data")
        if not data:
            break

        # Build author lookup from includes
        includes = payload.get("includes", {})
        users_list = includes.get("users", [])
        author_map: dict[str, dict[str, str]] = {}
        for user in users_list:
            if isinstance(user, dict):
                uid = str(user.get("id") or "")
                author_map[uid] = {
                    "name": str(user.get("name") or ""),
                    "username": str(user.get("username") or ""),
                }

        for tweet in data:
            if not isinstance(tweet, dict):
                continue
            tweet_id = str(tweet.get("id") or "").strip()
            text = str(tweet.get("text") or "").replace("\r", " ").replace("\n", " ").strip()
            if not text:
                continue

            author_id = str(tweet.get("author_id") or "")
            author_info = author_map.get(author_id, {})
            author_name = author_info.get("name", "")
            handle = author_info.get("username", "")
            tweet_url = f"https://x.com/{handle}/status/{tweet_id}" if handle and tweet_id else ""

            metrics = tweet.get("public_metrics") if isinstance(tweet.get("public_metrics"), dict) else {}

            bookmarks.append({
                "tweet_id": tweet_id,
                "text": text,
                "author_name": author_name,
                "handle": handle,
                "url": tweet_url,
                "created_at": str(tweet.get("created_at") or ""),
                "like_count": metrics.get("like_count", 0),
                "retweet_count": metrics.get("retweet_count", 0),
                "reply_count": metrics.get("reply_count", 0),
            })
            collected += 1
            if collected >= max_bookmarks:
                break

        meta = payload.get("meta", {})
        next_token = meta.get("next_token")
        if not next_token:
            break

    return bookmarks, warnings


# ---------------------------------------------------------------------------
# CSV import fallback
# ---------------------------------------------------------------------------

_CSV_URL_COLUMNS = ["url", "link", "tweet_url", "permalink"]
_CSV_TEXT_COLUMNS = ["text", "full_text", "tweet_text", "content", "body"]


def _find_column(header: list[str], candidates: list[str]) -> str | None:
    """Find the first matching column name (case-insensitive)."""
    lower_header = [h.lower().strip() for h in header]
    for candidate in candidates:
        if candidate.lower() in lower_header:
            return header[lower_header.index(candidate.lower())]
    return None


def _import_csv(csv_path: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Import bookmarks from a CSV export file."""
    warnings: list[str] = []
    bookmarks: list[dict[str, Any]] = []
    path = Path(csv_path)
    if not path.exists():
        warnings.append(f"CSV file not found: {csv_path}")
        return bookmarks, warnings

    try:
        with path.open(encoding="utf-8", errors="ignore", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                warnings.append(f"CSV file has no header row: {csv_path}")
                return bookmarks, warnings

            url_col = _find_column(list(reader.fieldnames), _CSV_URL_COLUMNS)
            text_col = _find_column(list(reader.fieldnames), _CSV_TEXT_COLUMNS)

            if not url_col and not text_col:
                warnings.append(
                    f"CSV missing expected columns. Found: {', '.join(reader.fieldnames)}. "
                    f"Expected at least one of: {', '.join(_CSV_URL_COLUMNS + _CSV_TEXT_COLUMNS)}"
                )
                return bookmarks, warnings

            for row in reader:
                url = str(row.get(url_col, "") if url_col else "").strip()
                text = str(row.get(text_col, "") if text_col else "").strip()
                if not url and not text:
                    continue
                bookmarks.append({
                    "tweet_id": "",
                    "text": text,
                    "author_name": str(row.get("author", row.get("name", ""))).strip(),
                    "handle": str(row.get("handle", row.get("username", row.get("screen_name", "")))).strip(),
                    "url": url,
                    "created_at": str(row.get("created_at", row.get("date", ""))).strip(),
                    "like_count": 0,
                    "retweet_count": 0,
                    "reply_count": 0,
                })
    except OSError as exc:
        warnings.append(f"CSV read error: {exc}")
    except csv.Error as exc:
        warnings.append(f"CSV parse error: {exc}")

    return bookmarks, warnings


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _load_state() -> dict[str, Any]:
    """Load ingest state from disk."""
    return _read_json(STATE_PATH, {
        "processed_ids": [],
        "total_ingested": 0,
        "last_run": None,
    })


def _save_state(state: dict[str, Any]) -> None:
    """Persist ingest state to disk."""
    _write_json(STATE_PATH, state)


def _dedup_bookmarks(
    bookmarks: list[dict[str, Any]],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Filter out already-processed bookmarks. Updates state in place."""
    processed_set = set(state.get("processed_ids", []))
    new_bookmarks: list[dict[str, Any]] = []
    for bm in bookmarks:
        url = str(bm.get("url") or bm.get("text") or "")
        bid = _bookmark_id(url)
        if bid not in processed_set:
            bm["bookmark_id"] = bid
            new_bookmarks.append(bm)
            processed_set.add(bid)
    state["processed_ids"] = list(processed_set)
    return new_bookmarks


# ---------------------------------------------------------------------------
# Knowledge graph update
# ---------------------------------------------------------------------------


def _update_knowledge_graph(bookmarks: list[dict[str, Any]]) -> int:
    """Append bookmark nodes to the knowledge graph. Returns count of new nodes added."""
    graph = _read_json(GRAPH_PATH, {"nodes": {}, "edges": []})
    if not isinstance(graph, dict):
        graph = {"nodes": {}, "edges": []}
    nodes = graph.get("nodes", {})
    if not isinstance(nodes, dict):
        nodes = {}

    added = 0
    for bm in bookmarks:
        bid = bm.get("bookmark_id") or _bookmark_id(str(bm.get("url") or bm.get("text") or ""))
        if bid in nodes:
            continue

        text = str(bm.get("text") or "")
        topic_tags = _classify_topic(text)
        score = _score_bookmark(text, topic_tags)
        url = str(bm.get("url") or "")
        date_str = str(bm.get("created_at") or _now_iso())

        nodes[bid] = {
            "id": bid,
            "type": "bookmark",
            "attributes": {
                "text": text,
                "author": str(bm.get("author_name") or ""),
                "handle": str(bm.get("handle") or ""),
                "url": url,
                "captured_at": date_str,
                "topic_tags": topic_tags,
                "action": "review",
                "signal_score": score,
            },
            "provenance": {
                "source": url,
                "timestamp": _now_iso(),
                "confidence": "MEDIUM",
            },
        }
        added += 1

    graph["nodes"] = nodes
    try:
        _write_json(GRAPH_PATH, graph)
    except OSError:
        pass
    return added


# ---------------------------------------------------------------------------
# Intake JSONL
# ---------------------------------------------------------------------------


def _write_intake_jsonl(bookmarks: list[dict[str, Any]]) -> int:
    """Append bookmark entries to intake JSONL for idea_intake processing."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with BOOKMARK_INTAKE_PATH.open("a", encoding="utf-8") as fh:
            for bm in bookmarks:
                entry = {
                    "url": str(bm.get("url") or ""),
                    "text": str(bm.get("text") or ""),
                    "source": "x_bookmark",
                    "captured_at": _now_iso(),
                }
                fh.write(json.dumps(entry) + "\n")
                written += 1
    except OSError:
        pass
    return written


# ---------------------------------------------------------------------------
# Enrichment pipeline (classify + score each bookmark)
# ---------------------------------------------------------------------------


def _enrich_bookmarks(bookmarks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add topic_tags and signal_score to each bookmark dict."""
    for bm in bookmarks:
        text = str(bm.get("text") or "")
        tags = _classify_topic(text)
        bm["topic_tags"] = tags
        bm["signal_score"] = _score_bookmark(text, tags)
    return bookmarks


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------


def _write_outputs(
    bookmarks: list[dict[str, Any]],
    new_count: int,
    warnings: list[str],
    source_label: str,
) -> tuple[Path, Path]:
    """Write markdown report and tool JSON output."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    md_path = OUTPUT_DIR / f"x_bookmark_ingest_{stamp}.md"
    json_path = TOOL_DIR / f"x_bookmark_ingest_{stamp}.json"

    # Sort bookmarks by score descending
    sorted_bm = sorted(bookmarks, key=lambda b: b.get("signal_score", 0), reverse=True)

    # Topic distribution
    topic_counts: dict[str, int] = {}
    for bm in sorted_bm:
        for tag in bm.get("topic_tags", []):
            topic_counts[tag] = topic_counts.get(tag, 0) + 1

    lines = [
        "# X Bookmark Ingest",
        "",
        f"Generated (UTC): {_now_iso()}",
        f"Source: {source_label}",
        "",
        "## Summary",
        f"- Bookmarks fetched: {len(bookmarks)}",
        f"- New (deduplicated): {new_count}",
        f"- Topics detected: {len(topic_counts)}",
    ]
    if warnings:
        lines.append(f"- Warnings: {len(warnings)}")

    lines.extend(["", "## Topic Distribution"])
    if not topic_counts:
        lines.append("- No topics detected.")
    else:
        for tag, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {tag}: {count}")

    lines.extend(["", "## Top Bookmarks"])
    if not sorted_bm:
        lines.append("- No bookmarks ingested.")
    for idx, bm in enumerate(sorted_bm[:30], start=1):
        handle = bm.get("handle") or "unknown"
        text_preview = str(bm.get("text") or "")
        if len(text_preview) > 120:
            text_preview = text_preview[:117] + "..."
        lines.append(
            f"{idx}. @{handle} | score={bm.get('signal_score', 0)} | "
            f"tags={','.join(bm.get('topic_tags', []) or ['-'])}"
        )
        lines.append(f"   {text_preview}")
        if bm.get("url"):
            lines.append(f"   {bm.get('url')}")

    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend([
        "",
        "## Governance Notes",
        "- Read-only bookmark collection. No social publishing endpoints are used.",
        "- Human review required before acting on any bookmark-derived ideas.",
        "",
    ])

    report = "\n".join(lines)
    try:
        md_path.write_text(report, encoding="utf-8")
    except OSError:
        pass

    payload = {
        "generated_at": _now_iso(),
        "source": source_label,
        "bookmark_count": len(bookmarks),
        "new_count": new_count,
        "topic_counts": topic_counts,
        "top_items": sorted_bm[:50],
        "warnings": warnings,
    }
    try:
        json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass

    return md_path, json_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="X/Twitter bookmark ingest and enrichment.")
    parser.add_argument(
        "--action",
        choices=["pull", "status", "import-csv"],
        default="pull",
        help="Action to perform (default: pull)",
    )
    parser.add_argument(
        "--max-bookmarks",
        type=int,
        default=MAX_BOOKMARKS_DEFAULT,
        help=f"Maximum bookmarks to fetch (default: {MAX_BOOKMARKS_DEFAULT})",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="X user ID (overrides PERMANENCE_X_USER_ID env var)",
    )
    parser.add_argument(
        "--csv-path",
        default=None,
        help="Path to CSV file for import-csv action",
    )
    args = parser.parse_args(argv)

    # -- Status action --
    if args.action == "status":
        state = _load_state()
        processed = len(state.get("processed_ids", []))
        total = state.get("total_ingested", 0)
        last_run = state.get("last_run", "never")
        print(f"Bookmark ingest state:")
        print(f"  Processed IDs: {processed}")
        print(f"  Total ingested: {total}")
        print(f"  Last run: {last_run}")
        return 0

    # -- Import CSV action --
    if args.action == "import-csv":
        if not args.csv_path:
            print("Error: --csv-path is required for import-csv action.")
            return 1

        bookmarks, warnings = _import_csv(args.csv_path)
        if not bookmarks:
            print("No bookmarks found in CSV file.")
            if warnings:
                for w in warnings:
                    print(f"  Warning: {w}")
            return 1

        state = _load_state()
        new_bookmarks = _dedup_bookmarks(bookmarks, state)
        new_bookmarks = _enrich_bookmarks(new_bookmarks)
        graph_added = _update_knowledge_graph(new_bookmarks)
        intake_written = _write_intake_jsonl(new_bookmarks)
        state["total_ingested"] = state.get("total_ingested", 0) + len(new_bookmarks)
        state["last_run"] = _now_iso()
        _save_state(state)

        md_path, json_path = _write_outputs(
            new_bookmarks,
            len(new_bookmarks),
            warnings,
            source_label=f"csv:{args.csv_path}",
        )

        print(f"CSV import complete: {len(new_bookmarks)} new bookmarks from {len(bookmarks)} rows.")
        print(f"  Knowledge graph nodes added: {graph_added}")
        print(f"  Intake entries written: {intake_written}")
        print(f"  Report: {md_path}")
        print(f"  Tool payload: {json_path}")
        return 0

    # -- Pull action (default) --
    user_id = args.user_id or os.getenv(X_USER_ID_ENV, "").strip()
    token = os.getenv(X_TOKEN_ENV, "").strip()

    if not user_id:
        print(
            f"Error: X user ID not set. Provide --user-id or set {X_USER_ID_ENV} environment variable."
        )
        return 1
    if not token:
        print(
            f"Error: X bearer token not set. Set {X_TOKEN_ENV} environment variable. "
            "Install with: python cli.py connector-keychain --target x-user-token --from-file ..."
        )
        return 1

    bookmarks, warnings = _fetch_bookmarks(user_id, token, args.max_bookmarks)
    if not bookmarks and warnings:
        print("No bookmarks fetched.")
        for w in warnings:
            print(f"  Warning: {w}")
        return 1

    state = _load_state()
    new_bookmarks = _dedup_bookmarks(bookmarks, state)
    new_bookmarks = _enrich_bookmarks(new_bookmarks)
    graph_added = _update_knowledge_graph(new_bookmarks)
    intake_written = _write_intake_jsonl(new_bookmarks)
    state["total_ingested"] = state.get("total_ingested", 0) + len(new_bookmarks)
    state["last_run"] = _now_iso()
    _save_state(state)

    md_path, json_path = _write_outputs(
        new_bookmarks,
        len(new_bookmarks),
        warnings,
        source_label=f"x_api:user_id={user_id}",
    )

    print(f"Bookmark ingest complete: {len(new_bookmarks)} new from {len(bookmarks)} fetched.")
    print(f"  Knowledge graph nodes added: {graph_added}")
    print(f"  Intake entries written: {intake_written}")
    print(f"  Report: {md_path}")
    print(f"  Tool payload: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
