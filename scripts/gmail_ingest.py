#!/usr/bin/env python3
"""
Gmail read-only ingestion for Email Agent triage.
Requires OAuth credentials.json and token.json.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.utils import log, BASE_DIR

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _default_paths() -> Dict[str, str]:
    working_dir = os.path.join(BASE_DIR, "memory", "working")
    email_dir = os.path.join(working_dir, "email")
    google_dir = os.path.join(working_dir, "google")
    os.makedirs(email_dir, exist_ok=True)
    os.makedirs(google_dir, exist_ok=True)
    return {
        "credentials": os.getenv(
            "PERMANENCE_GMAIL_CREDENTIALS",
            os.path.join(google_dir, "credentials.json"),
        ),
        "token": os.getenv(
            "PERMANENCE_GMAIL_TOKEN",
            os.path.join(google_dir, "token.json"),
        ),
        "output": os.getenv(
            "PERMANENCE_EMAIL_INBOX",
            os.path.join(email_dir, "inbox.json"),
        ),
    }


def _extract_headers(headers: List[Dict[str, Any]]) -> Dict[str, str]:
    mapping = {}
    for h in headers:
        name = h.get("name", "").lower()
        value = h.get("value", "")
        if name:
            mapping[name] = value
    return mapping


def _parse_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    payload = msg.get("payload", {})
    headers = _extract_headers(payload.get("headers", []))
    return {
        "id": msg.get("id"),
        "threadId": msg.get("threadId"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "labels": msg.get("labelIds", []),
    }


def _write_tool_memory(payload: Dict[str, Any]) -> str:
    tool_dir = os.getenv("PERMANENCE_TOOL_DIR", os.path.join(BASE_DIR, "memory", "tool"))
    os.makedirs(tool_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(tool_dir, f"gmail_ingest_{stamp}.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return path


def ingest_gmail(
    credentials_path: str,
    token_path: str,
    output_path: str,
    max_messages: int = 50,
    query: Optional[str] = None,
) -> str:
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Google API libraries not installed. Run pip install -r requirements.txt") from exc

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    list_kwargs: Dict[str, Any] = {"userId": "me", "maxResults": max_messages}
    if query:
        list_kwargs["q"] = query
    response = service.users().messages().list(**list_kwargs).execute()
    messages = response.get("messages", [])

    items: List[Dict[str, Any]] = []
    for msg in messages:
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["From", "To", "Subject", "Date"])
            .execute()
        )
        items.append(_parse_message(detail))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(items, f, indent=2)

    tool_path = _write_tool_memory({"query": query, "count": len(items), "items": items})
    log(f"Gmail ingest saved {len(items)} messages to {output_path}", level="INFO")
    log(f"Gmail ingest tool memory: {tool_path}", level="INFO")
    return output_path


def main() -> int:
    paths = _default_paths()
    parser = argparse.ArgumentParser(description="Ingest Gmail messages (read-only)")
    parser.add_argument("--credentials", default=paths["credentials"], help="OAuth credentials.json path")
    parser.add_argument("--token", default=paths["token"], help="OAuth token.json path")
    parser.add_argument("--output", default=paths["output"], help="Output inbox json path")
    parser.add_argument("--max", type=int, default=50, help="Max messages to fetch")
    parser.add_argument("--query", help="Gmail search query (optional)")
    args = parser.parse_args()

    if not os.path.exists(args.credentials):
        print(f"Missing credentials file: {args.credentials}")
        return 2

    ingest_gmail(
        credentials_path=args.credentials,
        token_path=args.token,
        output_path=args.output,
        max_messages=args.max,
        query=args.query,
    )
    print(f"Gmail inbox written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
