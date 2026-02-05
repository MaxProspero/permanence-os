#!/usr/bin/env python3
"""Adapter registry for Researcher ingestion pipelines."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from agents.researcher import ResearcherAgent, TOOL_DIR, DOC_DIR


@dataclass
class AdapterSpec:
    name: str
    description: str
    default_confidence: float
    run: Callable[..., List[Dict[str, Any]]]


def _tool_memory_adapter(**kwargs: Any) -> List[Dict[str, Any]]:
    agent = ResearcherAgent()
    return agent.compile_sources_from_tool_memory(
        tool_dir=kwargs.get("tool_dir", TOOL_DIR),
        output_path=kwargs.get("output_path"),
        default_confidence=kwargs.get("default_confidence", 0.5),
        max_entries=kwargs.get("max_entries", 100),
    )


def _documents_adapter(**kwargs: Any) -> List[Dict[str, Any]]:
    agent = ResearcherAgent()
    return agent.compile_sources_from_documents(
        doc_dir=kwargs.get("doc_dir", DOC_DIR),
        output_path=kwargs.get("output_path"),
        default_confidence=kwargs.get("default_confidence", 0.6),
        max_entries=kwargs.get("max_entries", 100),
        excerpt_chars=kwargs.get("excerpt_chars", 280),
    )


def _url_fetch_adapter(**kwargs: Any) -> List[Dict[str, Any]]:
    agent = ResearcherAgent()
    return agent.compile_sources_from_urls(
        urls=kwargs.get("urls"),
        urls_path=kwargs.get("urls_path"),
        output_path=kwargs.get("output_path"),
        default_confidence=kwargs.get("default_confidence", 0.5),
        max_entries=kwargs.get("max_entries", 50),
        excerpt_chars=kwargs.get("excerpt_chars", 280),
        timeout_sec=kwargs.get("timeout_sec", 15),
        max_bytes=kwargs.get("max_bytes", 1_000_000),
        user_agent=kwargs.get("user_agent", "PermanenceOS-Researcher/0.2"),
        tool_dir=kwargs.get("tool_dir", TOOL_DIR),
    )


def _web_search_adapter(**kwargs: Any) -> List[Dict[str, Any]]:
    agent = ResearcherAgent()
    return agent.compile_sources_from_web_search(
        query=kwargs.get("query", ""),
        output_path=kwargs.get("output_path"),
        default_confidence=kwargs.get("default_confidence", 0.5),
        max_entries=kwargs.get("max_entries", 5),
        excerpt_chars=kwargs.get("excerpt_chars", 280),
        timeout_sec=kwargs.get("timeout_sec", 20),
        tool_dir=kwargs.get("tool_dir", TOOL_DIR),
    )


def _google_docs_adapter(**kwargs: Any) -> List[Dict[str, Any]]:
    agent = ResearcherAgent()
    return agent.compile_sources_from_google_docs(
        doc_ids=kwargs.get("doc_ids"),
        doc_ids_path=kwargs.get("doc_ids_path"),
        folder_id=kwargs.get("folder_id"),
        output_path=kwargs.get("output_path"),
        default_confidence=kwargs.get("default_confidence", 0.6),
        max_entries=kwargs.get("max_entries", 50),
        excerpt_chars=kwargs.get("excerpt_chars", 280),
        max_doc_chars=kwargs.get("max_doc_chars", 50_000),
        credentials_path=kwargs.get("credentials_path"),
        token_path=kwargs.get("token_path"),
        tool_dir=kwargs.get("tool_dir", TOOL_DIR),
        cursor_path=kwargs.get("cursor_path"),
        max_seen=kwargs.get("max_seen", 5000),
        skip_failures=kwargs.get("skip_failures", False),
    )


def _drive_pdfs_adapter(**kwargs: Any) -> List[Dict[str, Any]]:
    agent = ResearcherAgent()
    return agent.compile_sources_from_drive_pdfs(
        file_ids=kwargs.get("file_ids"),
        file_ids_path=kwargs.get("file_ids_path"),
        folder_id=kwargs.get("folder_id"),
        output_path=kwargs.get("output_path"),
        default_confidence=kwargs.get("default_confidence", 0.6),
        max_entries=kwargs.get("max_entries", 50),
        excerpt_chars=kwargs.get("excerpt_chars", 280),
        max_pdf_bytes=kwargs.get("max_pdf_bytes", 8_000_000),
        max_seconds_per_file=kwargs.get("max_seconds_per_file", 25),
        credentials_path=kwargs.get("credentials_path"),
        token_path=kwargs.get("token_path"),
        tool_dir=kwargs.get("tool_dir", TOOL_DIR),
        cursor_path=kwargs.get("cursor_path"),
        max_seen=kwargs.get("max_seen", 5000),
        skip_failures=kwargs.get("skip_failures", False),
    )


def get_adapters() -> Dict[str, AdapterSpec]:
    return {
        "tool_memory": AdapterSpec(
            name="tool_memory",
            description="Ingest tool outputs from memory/tool",
            default_confidence=0.5,
            run=_tool_memory_adapter,
        ),
        "documents": AdapterSpec(
            name="documents",
            description="Ingest local documents from memory/working/documents",
            default_confidence=0.6,
            run=_documents_adapter,
        ),
        "url_fetch": AdapterSpec(
            name="url_fetch",
            description="Fetch URLs and emit sources with provenance",
            default_confidence=0.5,
            run=_url_fetch_adapter,
        ),
        "web_search": AdapterSpec(
            name="web_search",
            description="Web search via Tavily (requires TAVILY_API_KEY)",
            default_confidence=0.5,
            run=_web_search_adapter,
        ),
        "google_docs": AdapterSpec(
            name="google_docs",
            description="Ingest Google Docs via Drive/Docs API (read-only)",
            default_confidence=0.6,
            run=_google_docs_adapter,
        ),
        "drive_pdfs": AdapterSpec(
            name="drive_pdfs",
            description="Ingest PDF files from Google Drive (read-only)",
            default_confidence=0.6,
            run=_drive_pdfs_adapter,
        ),
    }


def run_adapter(name: str, **kwargs: Any) -> List[Dict[str, Any]]:
    adapters = get_adapters()
    if name not in adapters:
        raise ValueError(f"Unknown adapter: {name}")
    return adapters[name].run(**kwargs)


def list_adapters() -> List[AdapterSpec]:
    return list(get_adapters().values())
