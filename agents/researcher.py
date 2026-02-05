#!/usr/bin/env python3
"""
RESEARCHER AGENT
Gathers verified information with provenance. No speculation beyond sources.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import ipaddress
import io
import time
from urllib.parse import urlparse

from agents.utils import log, BASE_DIR

TOOL_DIR = os.getenv("PERMANENCE_TOOL_DIR", os.path.join(BASE_DIR, "memory", "tool"))
DOC_DIR = os.getenv(
    "PERMANENCE_DOCUMENTS_DIR", os.path.join(BASE_DIR, "memory", "working", "documents")
)
GOOGLE_DIR = os.getenv(
    "PERMANENCE_GOOGLE_DIR", os.path.join(BASE_DIR, "memory", "working", "google")
)


@dataclass
class SourceRecord:
    """Provenanced source entry."""
    source: str
    timestamp: str
    confidence: float
    notes: Optional[str] = None
    hash: Optional[str] = None
    origin: Optional[str] = None


class ResearcherAgent:
    """
    ROLE: Gather verified information with provenance.

    CONSTRAINTS:
    - Must cite sources with source + timestamp + confidence
    - Cannot speculate beyond sources
    - Cannot generate final content
    """

    def validate_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate that all sources include provenance fields."""
        if not sources:
            return {
                "ok": False,
                "errors": [{"index": None, "missing": ["source", "timestamp", "confidence"]}],
            }
        required = {"source", "timestamp", "confidence"}
        errors = []

        for idx, src in enumerate(sources):
            missing = required.difference(src.keys())
            if missing:
                errors.append({"index": idx, "missing": sorted(missing)})

        ok = len(errors) == 0
        log("Researcher validation complete", level="INFO")
        return {"ok": ok, "errors": errors}

    def compile_sources(self, _query: str) -> None:
        """
        Placeholder for external research.
        Explicitly unimplemented to avoid unsourced claims.
        """
        log("Researcher compile_sources called without tools", level="WARNING")
        raise NotImplementedError(
            "ResearcherAgent.compile_sources requires external tools and is not implemented."
        )

    def compile_sources_from_tool_memory(
        self,
        tool_dir: str = TOOL_DIR,
        output_path: Optional[str] = None,
        default_confidence: float = 0.5,
        max_entries: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Convert raw tool outputs into a sources list with provenance.
        """
        if not os.path.isdir(tool_dir):
            raise FileNotFoundError(f"Tool memory directory not found: {tool_dir}")

        sources: List[Dict[str, Any]] = []
        files = [f for f in os.listdir(tool_dir) if os.path.isfile(os.path.join(tool_dir, f))]
        files.sort(key=lambda f: os.path.getmtime(os.path.join(tool_dir, f)), reverse=True)

        for name in files:
            path = os.path.join(tool_dir, name)
            if len(sources) >= max_entries:
                break
            sources.extend(self._sources_from_file(path, default_confidence))
            if len(sources) >= max_entries:
                sources = sources[:max_entries]
                break

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(sources, f, indent=2)

        log(f"Compiled {len(sources)} sources from tool memory", level="INFO")
        return sources

    def compile_sources_from_documents(
        self,
        doc_dir: str = DOC_DIR,
        output_path: Optional[str] = None,
        default_confidence: float = 0.6,
        max_entries: int = 100,
        excerpt_chars: int = 280,
    ) -> List[Dict[str, Any]]:
        """
        Convert local documents into a sources list with provenance.
        Supports .txt, .md, .markdown, and .json files.
        """
        if not os.path.isdir(doc_dir):
            raise FileNotFoundError(f"Document directory not found: {doc_dir}")

        sources: List[Dict[str, Any]] = []
        files = [f for f in os.listdir(doc_dir) if os.path.isfile(os.path.join(doc_dir, f))]
        files.sort(key=lambda f: os.path.getmtime(os.path.join(doc_dir, f)), reverse=True)

        for name in files:
            if len(sources) >= max_entries:
                break
            path = os.path.join(doc_dir, name)
            sources.extend(self._sources_from_document(path, default_confidence, excerpt_chars))
            if len(sources) >= max_entries:
                sources = sources[:max_entries]
                break

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(sources, f, indent=2)

        log(f"Compiled {len(sources)} sources from documents", level="INFO")
        return sources

    def compile_sources_from_urls(
        self,
        urls: Optional[List[str]] = None,
        urls_path: Optional[str] = None,
        output_path: Optional[str] = None,
        default_confidence: float = 0.5,
        max_entries: int = 50,
        excerpt_chars: int = 280,
        timeout_sec: int = 15,
        max_bytes: int = 1_000_000,
        user_agent: str = "PermanenceOS-Researcher/0.2",
        tool_dir: str = TOOL_DIR,
    ) -> List[Dict[str, Any]]:
        """
        Fetch URLs and produce sources with provenance.
        Blocks localhost/private IPs by default.
        """
        url_list = urls or []
        if urls_path:
            url_list.extend(self._read_urls_file(urls_path))

        if not url_list:
            raise ValueError("No URLs provided")

        sources: List[Dict[str, Any]] = []
        os.makedirs(tool_dir, exist_ok=True)

        for idx, url in enumerate(url_list):
            if len(sources) >= max_entries:
                break
            if not self._safe_url(url):
                log(f"Skipping unsafe URL: {url}", level="WARNING")
                continue

            fetched = self._fetch_url(
                url,
                timeout_sec=timeout_sec,
                max_bytes=max_bytes,
                user_agent=user_agent,
            )
            if not fetched:
                continue

            fetched_at = datetime.now(timezone.utc).isoformat()
            content = fetched["content"]
            content_type = fetched.get("content_type")
            snippet = self._excerpt(fetched.get("text", ""), excerpt_chars)
            content_hash = self._hash_bytes(content)

            tool_payload = {
                "source": url,
                "timestamp": fetched_at,
                "confidence": default_confidence,
                "notes": snippet or "Fetched content",
                "hash": content_hash,
                "origin": "url_fetch",
                "content_type": content_type,
                "status": fetched.get("status"),
            }

            tool_name = f"url_fetch_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}_{idx}.json"
            tool_path = os.path.join(tool_dir, tool_name)
            try:
                with open(tool_path, "w") as f:
                    json.dump(tool_payload, f, indent=2)
            except OSError:
                pass

            sources.append(tool_payload)

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(sources, f, indent=2)

        log(f"Fetched {len(sources)} sources from URLs", level="INFO")
        return sources

    def compile_sources_from_web_search(
        self,
        query: str,
        output_path: Optional[str] = None,
        default_confidence: float = 0.5,
        max_entries: int = 5,
        excerpt_chars: int = 280,
        timeout_sec: int = 20,
        tool_dir: str = TOOL_DIR,
    ) -> List[Dict[str, Any]]:
        """
        Web search via Tavily API. Requires TAVILY_API_KEY.
        """
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY is not set")

        if not query or not query.strip():
            raise ValueError("Query is required for web search")

        try:
            import requests  # local import to keep dependency optional
        except ImportError:
            raise RuntimeError("requests is not installed")

        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": max_entries,
            "include_answer": False,
            "include_raw_content": False,
        }
        try:
            resp = requests.post("https://api.tavily.com/search", json=payload, timeout=timeout_sec)
        except requests.RequestException as exc:
            log(f"Web search failed: {exc}", level="ERROR")
            raise RuntimeError("Web search request failed") from exc

        if resp.status_code != 200:
            raise RuntimeError(f"Web search failed: {resp.status_code} {resp.text[:200]}")

        data = resp.json()
        results = data.get("results", [])
        sources: List[Dict[str, Any]] = []
        os.makedirs(tool_dir, exist_ok=True)
        fetched_at = datetime.now(timezone.utc).isoformat()

        for idx, item in enumerate(results[:max_entries]):
            url = item.get("url") or item.get("source") or "unknown"
            content = item.get("content") or item.get("snippet") or ""
            snippet = self._excerpt(content, excerpt_chars)
            raw = json.dumps(item, sort_keys=True).encode("utf-8")
            sources.append(
                {
                    "source": url,
                    "timestamp": fetched_at,
                    "confidence": default_confidence,
                    "notes": snippet,
                    "hash": self._hash_bytes(raw),
                    "origin": "tavily",
                }
            )

            tool_payload = {
                "query": query,
                "result_index": idx,
                "item": item,
                "timestamp": fetched_at,
            }
            tool_name = f"web_search_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}_{idx}.json"
            tool_path = os.path.join(tool_dir, tool_name)
            try:
                with open(tool_path, "w") as f:
                    json.dump(tool_payload, f, indent=2)
            except OSError:
                pass

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(sources, f, indent=2)

        log(f"Web search produced {len(sources)} sources", level="INFO")
        return sources

    def compile_sources_from_google_docs(
        self,
        doc_ids: Optional[List[str]] = None,
        doc_ids_path: Optional[str] = None,
        folder_id: Optional[str] = None,
        output_path: Optional[str] = None,
        default_confidence: float = 0.6,
        max_entries: int = 50,
        excerpt_chars: int = 280,
        max_doc_chars: int = 50_000,
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
        tool_dir: str = TOOL_DIR,
        cursor_path: Optional[str] = None,
        max_seen: int = 5000,
        skip_failures: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Ingest Google Docs into sources.json (read-only).
        Requires Google OAuth credentials and Docs/Drive APIs enabled.
        """
        ids: List[str] = []
        if doc_ids:
            ids.extend([d for d in doc_ids if d])
        if doc_ids_path:
            ids.extend(self._read_ids_file(doc_ids_path))

        credentials_path = credentials_path or os.path.join(GOOGLE_DIR, "credentials.json")
        token_path = token_path or os.path.join(GOOGLE_DIR, "docs_token.json")
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        os.makedirs(tool_dir, exist_ok=True)

        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Missing Google credentials file: {credentials_path}")

        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError("Google API libraries not installed. Run pip install -r requirements.txt") from exc

        scopes = [
            "https://www.googleapis.com/auth/documents.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]

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

        docs_service = build("docs", "v1", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        if folder_id:
            ids.extend(self._list_docs_in_folder(drive_service, folder_id))

        if not ids:
            raise ValueError("No Google Doc IDs provided")

        # Deduplicate while preserving order
        seen = set()
        unique_ids = []
        for doc_id in ids:
            if doc_id in seen:
                continue
            seen.add(doc_id)
            unique_ids.append(doc_id)

        sources: List[Dict[str, Any]] = []
        processed = self._load_cursor_ids(cursor_path) if cursor_path else set()
        now = datetime.now(timezone.utc)
        for doc_id in unique_ids:
            if len(sources) >= max_entries:
                break
            if doc_id in processed:
                continue
            try:
                doc = docs_service.documents().get(documentId=doc_id).execute()
            except Exception as exc:
                log(f"Failed to fetch Google Doc {doc_id}: {exc}", level="WARNING")
                if cursor_path and skip_failures:
                    processed.add(doc_id)
                continue
            title = doc.get("title") or "Untitled"
            text = self._extract_google_doc_text(doc, max_chars=max_doc_chars)
            excerpt = self._excerpt(text, excerpt_chars) if text else ""
            timestamp = now.isoformat()
            url = f"https://docs.google.com/document/d/{doc_id}/edit"
            content_hash = self._hash_bytes(text.encode("utf-8")) if text else None

            record = {
                "source": url,
                "timestamp": timestamp,
                "confidence": default_confidence,
                "notes": excerpt or f"Google Doc: {title}",
                "hash": content_hash,
                "origin": "google_docs",
                "doc_id": doc_id,
                "title": title,
            }
            sources.append(record)

            tool_payload = {
                "doc_id": doc_id,
                "title": title,
                "url": url,
                "timestamp": timestamp,
                "confidence": default_confidence,
                "excerpt": excerpt,
                "text_length": len(text),
                "hash": content_hash,
                "origin": "google_docs",
            }
            tool_name = f"google_doc_{doc_id}_{now.strftime('%Y%m%d-%H%M%S')}.json"
            tool_path = os.path.join(tool_dir, tool_name)
            try:
                with open(tool_path, "w") as f:
                    json.dump(tool_payload, f, indent=2)
            except OSError:
                pass
            if cursor_path:
                processed.add(doc_id)

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(sources, f, indent=2)

        if cursor_path:
            self._save_cursor_ids(cursor_path, processed, max_seen=max_seen)

        log(f"Compiled {len(sources)} sources from Google Docs", level="INFO")
        return sources

    def compile_sources_from_drive_pdfs(
        self,
        file_ids: Optional[List[str]] = None,
        file_ids_path: Optional[str] = None,
        folder_id: Optional[str] = None,
        output_path: Optional[str] = None,
        default_confidence: float = 0.6,
        max_entries: int = 50,
        excerpt_chars: int = 280,
        max_pdf_bytes: int = 8_000_000,
        max_seconds_per_file: int = 25,
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
        tool_dir: str = TOOL_DIR,
        cursor_path: Optional[str] = None,
        max_seen: int = 5000,
        skip_failures: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Ingest PDF files from Google Drive into sources.json (read-only).
        """
        ids: List[str] = []
        if file_ids:
            ids.extend([d for d in file_ids if d])
        if file_ids_path:
            ids.extend(self._read_ids_file(file_ids_path))

        credentials_path = credentials_path or os.path.join(GOOGLE_DIR, "credentials.json")
        token_path = token_path or os.path.join(GOOGLE_DIR, "drive_token.json")
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        os.makedirs(tool_dir, exist_ok=True)

        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Missing Google credentials file: {credentials_path}")

        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseDownload
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

        drive_service = build("drive", "v3", credentials=creds)

        if folder_id:
            ids.extend(self._list_pdfs_in_folder(drive_service, folder_id))

        if not ids:
            raise ValueError("No Drive PDF file IDs provided")

        # Deduplicate while preserving order
        seen = set()
        unique_ids = []
        for file_id in ids:
            if file_id in seen:
                continue
            seen.add(file_id)
            unique_ids.append(file_id)

        sources: List[Dict[str, Any]] = []
        processed = self._load_cursor_ids(cursor_path) if cursor_path else set()
        for file_id in unique_ids:
            if len(sources) >= max_entries:
                break
            if file_id in processed:
                continue
            try:
                meta = (
                    drive_service.files()
                    .get(fileId=file_id, fields="id,name,modifiedTime,mimeType,size")
                    .execute()
                )
            except Exception as exc:
                log(f"Failed to fetch Drive metadata for {file_id}: {exc}", level="WARNING")
                if cursor_path and skip_failures:
                    processed.add(file_id)
                continue
            if meta.get("mimeType") != "application/pdf":
                continue
            try:
                size = int(meta.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            if size and max_pdf_bytes and size > max_pdf_bytes:
                log(
                    f"Skipping Drive PDF {file_id} (size {size} > {max_pdf_bytes} bytes)",
                    level="WARNING",
                )
                if cursor_path:
                    processed.add(file_id)
                continue

            content = self._download_drive_file(
                drive_service,
                file_id,
                max_seconds=max_seconds_per_file,
            )
            if not content:
                if cursor_path and skip_failures:
                    processed.add(file_id)
                continue

            name = meta.get("name") or "drive.pdf"
            timestamp = meta.get("modifiedTime") or datetime.now(timezone.utc).isoformat()
            url = f"https://drive.google.com/file/d/{file_id}/view"

            text = ""
            try:
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(content))
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    if page_text:
                        text += page_text + "\n"
            except Exception:
                text = ""

            excerpt = self._excerpt(text, excerpt_chars) if text else ""
            content_hash = self._hash_bytes(content)

            record = {
                "source": url,
                "timestamp": timestamp,
                "confidence": default_confidence,
                "notes": excerpt or f"Drive PDF: {name}",
                "hash": content_hash,
                "origin": "drive_pdf",
                "file_id": file_id,
                "title": name,
            }
            sources.append(record)

            tool_payload = {
                "file_id": file_id,
                "name": name,
                "url": url,
                "timestamp": timestamp,
                "confidence": default_confidence,
                "excerpt": excerpt,
                "text_length": len(text),
                "hash": content_hash,
                "origin": "drive_pdf",
            }
            tool_name = f"drive_pdf_{file_id}_{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
            tool_path = os.path.join(tool_dir, tool_name)
            try:
                with open(tool_path, "w") as f:
                    json.dump(tool_payload, f, indent=2)
            except OSError:
                pass
            if cursor_path:
                processed.add(file_id)

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(sources, f, indent=2)

        if cursor_path:
            self._save_cursor_ids(cursor_path, processed, max_seen=max_seen)

        log(f"Compiled {len(sources)} sources from Drive PDFs", level="INFO")
        return sources
    def _sources_from_file(self, path: str, default_confidence: float) -> List[Dict[str, Any]]:
        try:
            if path.endswith(".json"):
                with open(path, "r") as f:
                    data = json.load(f)
                return self._sources_from_json(data, path, default_confidence)
        except (json.JSONDecodeError, OSError):
            pass

        # Fallback: treat as raw text output
        try:
            with open(path, "rb") as f:
                content = f.read()
            mtime = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
            return [
                {
                    "source": os.path.basename(path),
                    "timestamp": mtime,
                    "confidence": default_confidence,
                    "notes": "Raw tool output",
                    "hash": self._hash_bytes(content),
                    "origin": path,
                }
            ]
        except OSError:
            return []

    def _sources_from_json(
        self, data: Any, path: str, default_confidence: float
    ) -> List[Dict[str, Any]]:
        items = data if isinstance(data, list) else [data]
        results: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            source = item.get("source") or item.get("url") or item.get("title") or os.path.basename(path)
            timestamp = (
                item.get("timestamp")
                or item.get("retrieved_at")
                or item.get("date")
                or datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
            )
            confidence = item.get("confidence", default_confidence)
            notes = item.get("notes") or item.get("summary")
            raw = json.dumps(item, sort_keys=True).encode("utf-8")
            results.append(
                {
                    "source": source,
                    "timestamp": timestamp,
                    "confidence": confidence,
                    "notes": notes,
                    "hash": self._hash_bytes(raw),
                    "origin": path,
                }
            )
        return results

    def _sources_from_document(
        self, path: str, default_confidence: float, excerpt_chars: int
    ) -> List[Dict[str, Any]]:
        ext = os.path.splitext(path)[1].lower()
        if ext in {".txt", ".md", ".markdown"}:
            try:
                with open(path, "rb") as f:
                    content = f.read()
            except OSError:
                return []
            text = content.decode("utf-8", errors="ignore")
            excerpt = self._excerpt(text, excerpt_chars)
            mtime = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
            return [
                {
                    "source": os.path.basename(path),
                    "timestamp": mtime,
                    "confidence": default_confidence,
                    "notes": excerpt or "Document ingested (no excerpt)",
                    "hash": self._hash_bytes(content),
                    "origin": path,
                }
            ]

        if ext == ".pdf":
            try:
                with open(path, "rb") as f:
                    content = f.read()
            except OSError:
                return []
            mtime = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat()
            try:
                from pypdf import PdfReader
            except ImportError:
                return [
                    {
                        "source": os.path.basename(path),
                        "timestamp": mtime,
                        "confidence": default_confidence,
                        "notes": "PDF detected (install pypdf to extract text)",
                        "hash": self._hash_bytes(content),
                        "origin": path,
                    }
                ]
            text = ""
            try:
                reader = PdfReader(io.BytesIO(content))
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    if page_text:
                        text += page_text + "\n"
            except Exception:
                text = ""
            excerpt = self._excerpt(text, excerpt_chars) if text else ""
            return [
                {
                    "source": os.path.basename(path),
                    "timestamp": mtime,
                    "confidence": default_confidence,
                    "notes": excerpt or "PDF ingested (no extractable text)",
                    "hash": self._hash_bytes(content),
                    "origin": path,
                }
            ]

        if ext == ".json":
            try:
                with open(path, "r") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                return []
            return self._sources_from_json(data, path, default_confidence)

        return []

    def _excerpt(self, text: str, limit: int) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3].rstrip() + "..."

    def _safe_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.hostname
        if not host:
            return False
        if host in {"localhost", "127.0.0.1", "::1"}:
            return False
        if host.endswith(".local"):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            pass
        return True

    def _fetch_url(
        self,
        url: str,
        timeout_sec: int,
        max_bytes: int,
        user_agent: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            import requests  # local import to keep dependency optional
        except ImportError:
            log("requests not installed; cannot fetch URLs", level="ERROR")
            return None

        try:
            resp = requests.get(
                url,
                timeout=timeout_sec,
                headers={"User-Agent": user_agent},
            )
        except requests.RequestException:
            log(f"Fetch failed for URL: {url}", level="WARNING")
            return None

        content = resp.content[:max_bytes]
        text = ""
        try:
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            text = ""

        if text:
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(text, "html.parser")
                text = soup.get_text(" ", strip=True)
            except Exception:
                pass

        return {
            "status": resp.status_code,
            "content_type": resp.headers.get("Content-Type", ""),
            "content": content,
            "text": text,
        }

    def _read_urls_file(self, path: str) -> List[str]:
        try:
            with open(path, "r") as f:
                data = f.read().strip()
        except OSError:
            return []
        if not data:
            return []
        if path.endswith(".json"):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, list):
                    return [str(u).strip() for u in parsed if str(u).strip()]
            except json.JSONDecodeError:
                return []
        return [line.strip() for line in data.splitlines() if line.strip()]

    def _read_ids_file(self, path: str) -> List[str]:
        try:
            with open(path, "r") as f:
                data = f.read().strip()
        except OSError:
            return []
        if not data:
            return []
        if path.endswith(".json"):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, list):
                    return [str(d).strip() for d in parsed if str(d).strip()]
            except json.JSONDecodeError:
                return []
        return [line.strip() for line in data.splitlines() if line.strip()]

    def _list_docs_in_folder(self, drive_service: Any, folder_id: str) -> List[str]:
        query = (
            f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
        )
        ids: List[str] = []
        page_token = None
        while True:
            response = (
                drive_service.files()
                .list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, modifiedTime)",
                    pageToken=page_token,
                )
                .execute()
            )
            files = response.get("files", [])
            # Sort newest first
            files.sort(key=lambda f: f.get("modifiedTime", ""), reverse=True)
            ids.extend([f.get("id") for f in files if f.get("id")])
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return ids

    def _list_pdfs_in_folder(self, drive_service: Any, folder_id: str) -> List[str]:
        query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
        ids: List[str] = []
        page_token = None
        while True:
            response = (
                drive_service.files()
                .list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, modifiedTime)",
                    pageToken=page_token,
                )
                .execute()
            )
            files = response.get("files", [])
            files.sort(key=lambda f: f.get("modifiedTime", ""), reverse=True)
            ids.extend([f.get("id") for f in files if f.get("id")])
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return ids

    @staticmethod
    def _download_drive_file(
        drive_service: Any,
        file_id: str,
        max_seconds: int = 25,
    ) -> Optional[bytes]:
        try:
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError:
            return None
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        started = time.monotonic()
        try:
            while not done:
                _status, done = downloader.next_chunk()
                if max_seconds and (time.monotonic() - started) > max_seconds:
                    return None
        except Exception:
            return None
        return fh.getvalue()

    def _extract_google_doc_text(self, doc: Dict[str, Any], max_chars: int = 50_000) -> str:
        content = doc.get("body", {}).get("content", [])
        parts: List[str] = []
        total = 0
        for block in content:
            paragraph = block.get("paragraph")
            if not paragraph:
                continue
            for elem in paragraph.get("elements", []):
                text_run = elem.get("textRun")
                if text_run and text_run.get("content"):
                    chunk = text_run["content"]
                    parts.append(chunk)
                    total += len(chunk)
                    if max_chars and total >= max_chars:
                        return "".join(parts).strip()
        return "".join(parts).strip()

    @staticmethod
    def _load_cursor_ids(path: Optional[str]) -> set[str]:
        if not path or not os.path.exists(path):
            return set()
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return set()
        if isinstance(data, list):
            return set(str(x) for x in data)
        if isinstance(data, dict) and "ids" in data and isinstance(data["ids"], list):
            return set(str(x) for x in data["ids"])
        return set()

    @staticmethod
    def _save_cursor_ids(path: str, ids: set[str], max_seen: int = 5000) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ordered = list(ids)
        if max_seen and len(ordered) > max_seen:
            ordered = ordered[-max_seen:]
        payload = {"ids": ordered, "updated_at": datetime.now(timezone.utc).isoformat()}
        try:
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
        except OSError:
            pass

    def _hash_bytes(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


if __name__ == "__main__":
    ra = ResearcherAgent()
    sample = [
        {"source": "example", "timestamp": datetime.now(timezone.utc).isoformat(), "confidence": 0.7}
    ]
    print(ra.validate_sources(sample))
