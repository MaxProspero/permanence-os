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
from urllib.parse import urlparse

from agents.utils import log, BASE_DIR

TOOL_DIR = os.getenv("PERMANENCE_TOOL_DIR", os.path.join(BASE_DIR, "memory", "tool"))
DOC_DIR = os.getenv(
    "PERMANENCE_DOCUMENTS_DIR", os.path.join(BASE_DIR, "memory", "working", "documents")
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

            tool_name = f"url_fetch_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}_{idx}.json"
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
            tool_name = f"web_search_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}_{idx}.json"
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

    def _hash_bytes(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


if __name__ == "__main__":
    ra = ResearcherAgent()
    sample = [
        {"source": "example", "timestamp": datetime.now(timezone.utc).isoformat(), "confidence": 0.7}
    ]
    print(ra.validate_sources(sample))
