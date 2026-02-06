#!/usr/bin/env python3
"""
Sync NotebookLM exports from a Google Drive folder into storage archives.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from agents.researcher import GOOGLE_DIR  # noqa: E402
from agents.utils import log  # noqa: E402
from core.storage import storage  # noqa: E402


def _safe_name(name: str) -> str:
    name = name.strip().replace("/", "_")
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return name or "notebooklm_export"


def _load_cursor(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save_cursor(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _build_drive_service(credentials_path: str, token_path: str):
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Google API libraries not installed. Run pip install -r requirements.txt") from exc

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def _build_docs_service(credentials_path: str, token_path: str):
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Google API libraries not installed. Run pip install -r requirements.txt") from exc

    scopes = ["https://www.googleapis.com/auth/documents.readonly"]
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return build("docs", "v1", credentials=creds)


def _extract_doc_text(doc: dict) -> str:
    parts: list[str] = []
    body = doc.get("body", {}).get("content", [])
    for element in body:
        if "paragraph" in element:
            for pe in element["paragraph"].get("elements", []):
                text_run = pe.get("textRun", {}).get("content")
                if text_run:
                    parts.append(text_run)
        elif "table" in element:
            for row in element["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    for ce in cell.get("content", []):
                        if "paragraph" in ce:
                            for pe in ce["paragraph"].get("elements", []):
                                text_run = pe.get("textRun", {}).get("content")
                                if text_run:
                                    parts.append(text_run)
    return "".join(parts).strip()


def _split_text(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        chunk = text[start : start + max_chars].strip()
        if chunk:
            chunks.append(chunk)
        start += max_chars
    return chunks


def _iter_folder_files(drive_service, folder_id: str):
    page_token = None
    query = f"'{folder_id}' in parents and trashed=false"
    fields = "nextPageToken, files(id,name,mimeType,modifiedTime,size)"
    while True:
        resp = (
            drive_service.files()
            .list(q=query, fields=fields, pageToken=page_token, pageSize=100)
            .execute()
        )
        for item in resp.get("files", []):
            yield item
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def _download_file(drive_service, file_id: str, mime_type: str):
    from googleapiclient.http import MediaIoBaseDownload

    fh = io.BytesIO()
    if mime_type.startswith("application/vnd.google-apps."):
        request = drive_service.files().export_media(fileId=file_id, mimeType="application/pdf")
    else:
        request = drive_service.files().get_media(fileId=file_id)

    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue()


def _export_text(drive_service, file_id: str) -> str:
    from googleapiclient.http import MediaIoBaseDownload

    fh = io.BytesIO()
    request = drive_service.files().export_media(fileId=file_id, mimeType="text/plain")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue().decode("utf-8", errors="ignore").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync NotebookLM exports from Drive")
    parser.add_argument("--folder-id", help="Google Drive folder ID")
    parser.add_argument("--credentials", help="Google OAuth credentials.json path")
    parser.add_argument("--token", help="Google OAuth token path")
    parser.add_argument("--max-files", type=int, default=50, help="Max files to sync per run")
    parser.add_argument("--max-seconds", type=int, default=120, help="Max seconds per run")
    parser.add_argument("--max-bytes", type=int, default=25_000_000, help="Skip files larger than this")
    parser.add_argument("--split-max-chars", type=int, default=40_000, help="Max chars per split part")
    parser.add_argument("--cursor", help="Cursor file path")
    args = parser.parse_args()

    folder_id = args.folder_id or os.getenv("PERMANENCE_NOTEBOOKLM_FOLDER_ID")
    if not folder_id:
        print("Missing folder ID. Provide --folder-id or set PERMANENCE_NOTEBOOKLM_FOLDER_ID.")
        return 1

    credentials_path = args.credentials or os.path.join(GOOGLE_DIR, "credentials.json")
    token_path = args.token or os.path.join(GOOGLE_DIR, "drive_token.json")
    if not os.path.exists(credentials_path):
        print(f"Missing Google credentials: {credentials_path}")
        return 1

    cursor_path = Path(args.cursor) if args.cursor else storage.paths.archives_notebooklm / ".notebooklm_cursor.json"
    cursor = _load_cursor(cursor_path)

    drive_service = _build_drive_service(credentials_path, token_path)
    docs_service = None
    start_time = time.time()
    synced = 0
    split_count = 0
    skipped = 0
    failures: list[dict] = []

    for item in _iter_folder_files(drive_service, folder_id):
        if synced >= args.max_files:
            break
        if time.time() - start_time > args.max_seconds:
            break

        file_id = item.get("id")
        name = item.get("name") or "notebooklm_export"
        mime_type = item.get("mimeType") or ""
        modified = item.get("modifiedTime") or ""
        size = int(item.get("size") or 0)

        if file_id and file_id in cursor and modified and modified <= cursor[file_id]:
            skipped += 1
            continue
        if size and size > args.max_bytes:
            log(f"Skipping {name} (size {size} > {args.max_bytes})", level="WARNING")
            skipped += 1
            cursor[file_id] = modified
            continue

        try:
            content = _download_file(drive_service, file_id, mime_type)
        except Exception as exc:
            exc_text = str(exc)
            is_export_limit = "exportSizeLimitExceeded" in exc_text
            is_doc = mime_type == "application/vnd.google-apps.document"
            if is_export_limit and is_doc:
                try:
                    if docs_service is None:
                        docs_service = _build_docs_service(credentials_path, token_path)
                    doc = docs_service.documents().get(documentId=file_id).execute()
                    text = _extract_doc_text(doc)
                    if not text:
                        raise ValueError("Empty document text")
                    chunks = _split_text(text, args.split_max_chars)
                    if not chunks:
                        raise ValueError("Unable to split document text")
                    base = _safe_name(os.path.splitext(name)[0])
                    for idx, chunk in enumerate(chunks, 1):
                        dest = storage.paths.archives_notebooklm / f"{base}__{file_id}__part{idx:02d}.md"
                        dest.write_text(chunk)
                    cursor[file_id] = modified
                    split_count += 1
                    log(f"Split {name} into {len(chunks)} parts", level="INFO")
                    continue
                except Exception as split_exc:
                    log(f"Failed to split {name}: {split_exc}", level="WARNING")
                    # Fallback: export as plain text and split locally.
                    try:
                        text = _export_text(drive_service, file_id)
                        if not text:
                            raise ValueError("Empty export text")
                        chunks = _split_text(text, args.split_max_chars)
                        if not chunks:
                            raise ValueError("Unable to split export text")
                        base = _safe_name(os.path.splitext(name)[0])
                        for idx, chunk in enumerate(chunks, 1):
                            dest = storage.paths.archives_notebooklm / f"{base}__{file_id}__part{idx:02d}.md"
                            dest.write_text(chunk)
                        cursor[file_id] = modified
                        split_count += 1
                        log(f"Split {name} via text export into {len(chunks)} parts", level="INFO")
                        continue
                    except Exception as export_exc:
                        log(f"Text export split failed for {name}: {export_exc}", level="WARNING")
            failures.append(
                {
                    "file_id": file_id,
                    "name": name,
                    "reason": exc_text,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            log(f"Failed to download {name}: {exc}", level="WARNING")
            continue

        base = _safe_name(os.path.splitext(name)[0])
        ext = ".pdf" if mime_type.startswith("application/vnd.google-apps.") else os.path.splitext(name)[1]
        if not ext:
            ext = ".bin"
        dest = storage.paths.archives_notebooklm / f"{base}__{file_id}{ext}"
        dest.write_bytes(content)

        cursor[file_id] = modified
        synced += 1

    _save_cursor(cursor_path, cursor)

    if failures:
        fail_path = storage.paths.archives_notebooklm / "failed.json"
        existing = []
        if fail_path.exists():
            try:
                existing = json.loads(fail_path.read_text())
            except Exception:
                existing = []
        merged = (existing + failures)[-500:]
        fail_path.write_text(json.dumps(merged, indent=2))

    log(
        f"NotebookLM sync complete: {synced} downloaded, {split_count} split, {skipped} skipped",
        level="INFO",
    )
    print(f"NotebookLM sync complete: {synced} downloaded, {split_count} split, {skipped} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
