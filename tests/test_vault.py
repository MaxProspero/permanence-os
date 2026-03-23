#!/usr/bin/env python3
"""
Tests for the Knowledge Vault system.

Covers: note CRUD, wiki-link extraction, backlink queries, tag parsing,
daily notes, search, graph export, CLI argument parsing, and edge cases.
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the project root is on the path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "scripts"))
sys.path.insert(0, str(BASE_DIR / "core"))

from vault import (
    WIKI_LINK_RE,
    TAG_RE,
    Vault,
    _build_parser,
    _title_to_filename,
    _filename_to_title,
    extract_wiki_links,
    extract_tags,
    main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_vault(tmp_path):
    """Create a Vault instance with temporary storage."""
    vault_dir = tmp_path / "vault"
    index_db = str(tmp_path / "vault_index.db")
    entity_db = str(tmp_path / "entity_graph.db")

    # Initialize entity graph for integration tests
    try:
        from entity_graph import EntityGraph
        EntityGraph(db_path=entity_db)
    except Exception:
        pass

    v = Vault(
        vault_dir=str(vault_dir),
        index_db_path=index_db,
        entity_db_path=entity_db,
    )
    return v


@pytest.fixture
def vault_with_notes(tmp_vault):
    """Vault pre-populated with a few test notes."""
    tmp_vault.create_note(
        title="Project Alpha",
        body="This is about #project-alpha and links to [[Meeting Notes]].",
        tags=["work"],
    )
    tmp_vault.create_note(
        title="Meeting Notes",
        body="Discussed [[Project Alpha]] and [[Budget Review]].\n#meeting #work",
    )
    tmp_vault.create_note(
        title="Budget Review",
        body="Financials for Q1. See [[Project Alpha|the main project]].\n#finance",
    )
    return tmp_vault


# ---------------------------------------------------------------------------
# Wiki-link extraction
# ---------------------------------------------------------------------------

class TestWikiLinks:

    def test_simple_link(self):
        links = extract_wiki_links("Check out [[My Note]] for details.")
        assert len(links) == 1
        assert links[0]["target"] == "My Note"
        assert links[0]["display"] == "My Note"

    def test_alias_link(self):
        links = extract_wiki_links("See [[My Note|this note]] here.")
        assert len(links) == 1
        assert links[0]["target"] == "My Note"
        assert links[0]["display"] == "this note"

    def test_multiple_links(self):
        text = "Links to [[Note A]], [[Note B|B]], and [[Note C]]."
        links = extract_wiki_links(text)
        assert len(links) == 3
        targets = [l["target"] for l in links]
        assert "Note A" in targets
        assert "Note B" in targets
        assert "Note C" in targets

    def test_no_links(self):
        links = extract_wiki_links("No links here.")
        assert links == []

    def test_empty_string(self):
        links = extract_wiki_links("")
        assert links == []

    def test_nested_brackets_ignored(self):
        # Malformed links should not crash
        links = extract_wiki_links("Text [[ ]] more text")
        assert len(links) == 0

    def test_link_with_spaces(self):
        links = extract_wiki_links("[[  Spaced Title  ]]")
        assert len(links) == 1
        assert links[0]["target"] == "Spaced Title"


# ---------------------------------------------------------------------------
# Tag extraction
# ---------------------------------------------------------------------------

class TestTags:

    def test_simple_tag(self):
        tags = extract_tags("This is a #test note.")
        assert "test" in tags

    def test_hyphenated_tag(self):
        tags = extract_tags("Working on #project-alpha today.")
        assert "project-alpha" in tags

    def test_underscored_tag(self):
        tags = extract_tags("See #my_tag for details.")
        assert "my_tag" in tags

    def test_multiple_tags(self):
        tags = extract_tags("#alpha #beta #gamma")
        assert len(tags) == 3
        assert "alpha" in tags
        assert "beta" in tags
        assert "gamma" in tags

    def test_no_tags(self):
        tags = extract_tags("No tags here.")
        assert tags == []

    def test_deduplication(self):
        tags = extract_tags("#alpha some text #alpha again")
        assert tags.count("alpha") == 1

    def test_tag_at_line_start(self):
        tags = extract_tags("#daily\nSome content")
        assert "daily" in tags

    def test_numeric_only_tag_ignored(self):
        # Tags starting with a letter only
        tags = extract_tags("#123 is not a tag")
        assert len(tags) == 0

    def test_tag_lowercased(self):
        tags = extract_tags("#MyTag is capitalized")
        assert "mytag" in tags


# ---------------------------------------------------------------------------
# Filename conversion
# ---------------------------------------------------------------------------

class TestFilenames:

    def test_simple_title(self):
        assert _title_to_filename("My Note") == "My-Note.md"

    def test_special_chars(self):
        result = _title_to_filename("A/B: Test?")
        assert "/" not in result
        assert ":" not in result
        assert "?" not in result
        assert result.endswith(".md")

    def test_empty_title(self):
        assert _title_to_filename("") == "untitled.md"

    def test_filename_to_title(self):
        assert _filename_to_title("My-Note.md") == "My Note"

    def test_date_filename(self):
        assert _title_to_filename("2026-03-22") == "2026-03-22.md"


# ---------------------------------------------------------------------------
# Note CRUD
# ---------------------------------------------------------------------------

class TestNoteCRUD:

    def test_create_note(self, tmp_vault):
        result = tmp_vault.create_note(
            title="First Note",
            body="Hello world. #test",
            tags=["intro"],
        )
        assert result["ok"] is True
        assert result["title"] == "First Note"
        assert "test" in result["tags"]
        assert "intro" in result["tags"]
        assert len(result["id"]) == 12

    def test_create_note_writes_file(self, tmp_vault):
        tmp_vault.create_note(title="File Check", body="Content here.")
        filepath = tmp_vault.vault_dir / "File-Check.md"
        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        assert "Content here." in content
        assert "title: File Check" in content

    def test_create_duplicate_fails(self, tmp_vault):
        tmp_vault.create_note(title="Duplicate", body="First version.")
        result = tmp_vault.create_note(title="Duplicate", body="Second version.")
        assert result["ok"] is False
        assert "already exists" in result["error"]

    def test_create_empty_title_fails(self, tmp_vault):
        result = tmp_vault.create_note(title="", body="No title.")
        assert result["ok"] is False

    def test_get_note_by_title(self, tmp_vault):
        tmp_vault.create_note(title="Retrievable", body="Get me.")
        note = tmp_vault.get_note(title="Retrievable")
        assert note is not None
        assert note["title"] == "Retrievable"
        assert "Get me." in note["body"]

    def test_get_note_by_id(self, tmp_vault):
        result = tmp_vault.create_note(title="By ID", body="ID lookup.")
        note = tmp_vault.get_note(note_id=result["id"])
        assert note is not None
        assert note["title"] == "By ID"

    def test_get_nonexistent_note(self, tmp_vault):
        note = tmp_vault.get_note(title="Does Not Exist")
        assert note is None

    def test_update_note_body(self, tmp_vault):
        tmp_vault.create_note(title="Updatable", body="Original.")
        result = tmp_vault.update_note(title="Updatable", body="Updated content.")
        assert result["ok"] is True
        note = tmp_vault.get_note(title="Updatable")
        assert "Updated content." in note["body"]

    def test_update_note_title(self, tmp_vault):
        tmp_vault.create_note(title="Old Title", body="Content.")
        result = tmp_vault.update_note(title="Old Title", new_title="New Title")
        assert result["ok"] is True
        assert tmp_vault.get_note(title="New Title") is not None
        assert tmp_vault.get_note(title="Old Title") is None

    def test_update_nonexistent_fails(self, tmp_vault):
        result = tmp_vault.update_note(title="Ghost", body="Nothing.")
        assert result["ok"] is False

    def test_delete_note(self, tmp_vault):
        tmp_vault.create_note(title="Deletable", body="Remove me.")
        result = tmp_vault.delete_note(title="Deletable")
        assert result["ok"] is True
        assert tmp_vault.get_note(title="Deletable") is None

    def test_delete_removes_file(self, tmp_vault):
        tmp_vault.create_note(title="File Delete", body="Gone.")
        filepath = tmp_vault.vault_dir / "File-Delete.md"
        assert filepath.exists()
        tmp_vault.delete_note(title="File Delete")
        assert not filepath.exists()

    def test_delete_nonexistent_fails(self, tmp_vault):
        result = tmp_vault.delete_note(title="Nope")
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Backlinks
# ---------------------------------------------------------------------------

class TestBacklinks:

    def test_backlinks_found(self, vault_with_notes):
        backlinks = vault_with_notes.get_backlinks(title="Project Alpha")
        titles = [bl["title"] for bl in backlinks]
        assert "Meeting Notes" in titles
        assert "Budget Review" in titles

    def test_backlinks_with_context(self, vault_with_notes):
        backlinks = vault_with_notes.get_backlinks(title="Project Alpha")
        for bl in backlinks:
            assert bl.get("context")
            assert "[[Project Alpha" in bl["context"]

    def test_no_backlinks(self, vault_with_notes):
        # Create an orphan note
        vault_with_notes.create_note(title="Orphan", body="No one links here.")
        backlinks = vault_with_notes.get_backlinks(title="Orphan")
        assert len(backlinks) == 0

    def test_backlinks_empty_title(self, vault_with_notes):
        backlinks = vault_with_notes.get_backlinks(title="")
        assert backlinks == []


# ---------------------------------------------------------------------------
# Daily notes
# ---------------------------------------------------------------------------

class TestDailyNotes:

    def test_create_daily_note(self, tmp_vault):
        result = tmp_vault.create_daily_note(date="2026-03-22")
        assert result["ok"] is True
        assert result["title"] == "2026-03-22"
        assert result["is_new"] is True

    def test_daily_note_idempotent(self, tmp_vault):
        tmp_vault.create_daily_note(date="2026-03-22")
        result = tmp_vault.create_daily_note(date="2026-03-22")
        assert result["ok"] is True
        assert result["is_new"] is False

    def test_daily_note_has_template(self, tmp_vault):
        tmp_vault.create_daily_note(date="2026-03-22")
        note = tmp_vault.get_note(title="2026-03-22")
        assert "## Tasks" in note["body"]
        assert "## Notes" in note["body"]
        assert "## Reflections" in note["body"]

    def test_daily_note_links_to_previous(self, tmp_vault):
        tmp_vault.create_daily_note(date="2026-03-22")
        note = tmp_vault.get_note(title="2026-03-22")
        assert "[[2026-03-21]]" in note["body"]

    def test_daily_note_has_daily_tag(self, tmp_vault):
        tmp_vault.create_daily_note(date="2026-03-22")
        note = tmp_vault.get_note(title="2026-03-22")
        assert "daily" in note["tags"]

    def test_daily_note_invalid_date(self, tmp_vault):
        result = tmp_vault.create_daily_note(date="not-a-date")
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearch:

    def test_search_by_title(self, vault_with_notes):
        results = vault_with_notes.search(query="Project Alpha")
        titles = [r["title"] for r in results]
        assert "Project Alpha" in titles

    def test_search_by_body_content(self, vault_with_notes):
        results = vault_with_notes.search(query="Financials")
        titles = [r["title"] for r in results]
        assert "Budget Review" in titles

    def test_search_by_tag(self, vault_with_notes):
        results = vault_with_notes.search(query="", tag="work")
        assert len(results) >= 1
        for r in results:
            assert "work" in [t.lower() for t in r["tags"]]

    def test_search_no_results(self, vault_with_notes):
        results = vault_with_notes.search(query="xyznonexistent")
        assert len(results) == 0

    def test_search_empty_query(self, tmp_vault):
        results = tmp_vault.search(query="")
        assert results == []

    def test_search_respects_limit(self, vault_with_notes):
        results = vault_with_notes.search(query="Note", limit=1)
        assert len(results) <= 1


# ---------------------------------------------------------------------------
# Tags listing
# ---------------------------------------------------------------------------

class TestTagListing:

    def test_list_tags(self, vault_with_notes):
        tags = vault_with_notes.list_tags()
        assert "work" in tags
        assert tags["work"] >= 2  # both Project Alpha and Meeting Notes have #work

    def test_list_tags_empty_vault(self, tmp_vault):
        tags = tmp_vault.list_tags()
        assert tags == {}


# ---------------------------------------------------------------------------
# Graph export
# ---------------------------------------------------------------------------

class TestGraphExport:

    def test_graph_has_nodes(self, vault_with_notes):
        graph = vault_with_notes.export_graph()
        assert len(graph["nodes"]) >= 3

    def test_graph_has_edges(self, vault_with_notes):
        graph = vault_with_notes.export_graph()
        assert len(graph["edges"]) >= 1

    def test_graph_edge_structure(self, vault_with_notes):
        graph = vault_with_notes.export_graph()
        for edge in graph["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "source_title" in edge
            assert "target_title" in edge

    def test_graph_empty_vault(self, tmp_vault):
        graph = tmp_vault.export_graph()
        assert graph["nodes"] == []
        assert graph["edges"] == []


# ---------------------------------------------------------------------------
# List notes
# ---------------------------------------------------------------------------

class TestListNotes:

    def test_list_all(self, vault_with_notes):
        notes = vault_with_notes.list_notes()
        assert len(notes) >= 3

    def test_list_by_tag(self, vault_with_notes):
        notes = vault_with_notes.list_notes(tag="finance")
        assert len(notes) >= 1
        assert notes[0]["title"] == "Budget Review"

    def test_list_respects_limit(self, vault_with_notes):
        notes = vault_with_notes.list_notes(limit=1)
        assert len(notes) == 1

    def test_list_empty_vault(self, tmp_vault):
        notes = tmp_vault.list_notes()
        assert notes == []


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

class TestCLI:

    def test_create_args(self):
        parser = _build_parser()
        args = parser.parse_args(["--action", "create", "--title", "Test", "--body", "Body"])
        assert args.action == "create"
        assert args.title == "Test"
        assert args.body == "Body"

    def test_search_args(self):
        parser = _build_parser()
        args = parser.parse_args(["--action", "search", "--query", "hello", "--limit", "5"])
        assert args.action == "search"
        assert args.query == "hello"
        assert args.limit == 5

    def test_daily_args(self):
        parser = _build_parser()
        args = parser.parse_args(["--action", "daily", "--date", "2026-03-22"])
        assert args.action == "daily"
        assert args.date == "2026-03-22"

    def test_cli_create(self, tmp_path):
        vault_dir = str(tmp_path / "vault")
        index_db = str(tmp_path / "index.db")
        result = main([
            "--action", "create",
            "--title", "CLI Note",
            "--body", "Created via CLI",
            "--vault-dir", vault_dir,
            "--index-db", index_db,
        ])
        assert result == 0

    def test_cli_get_not_found(self, tmp_path):
        vault_dir = str(tmp_path / "vault")
        index_db = str(tmp_path / "index.db")
        result = main([
            "--action", "get",
            "--title", "Nonexistent",
            "--vault-dir", vault_dir,
            "--index-db", index_db,
        ])
        assert result == 1


# ---------------------------------------------------------------------------
# Reindex
# ---------------------------------------------------------------------------

class TestReindex:

    def test_reindex_recovers_notes(self, tmp_vault):
        # Create notes, then clear index, then reindex
        tmp_vault.create_note(title="Indexed Note", body="Recoverable.")
        conn = tmp_vault._index_conn()
        conn.execute("DELETE FROM vault_notes")
        conn.commit()

        # Verify index is empty
        notes = tmp_vault.list_notes()
        assert len(notes) == 0

        # Reindex
        result = tmp_vault.reindex()
        assert result["ok"] is True
        assert result["indexed"] >= 1

        # Should be back
        notes = tmp_vault.list_notes()
        assert len(notes) >= 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_note_with_no_body(self, tmp_vault):
        result = tmp_vault.create_note(title="Empty Body")
        assert result["ok"] is True
        note = tmp_vault.get_note(title="Empty Body")
        assert note is not None
        assert note["body"] == ""

    def test_note_with_unicode(self, tmp_vault):
        result = tmp_vault.create_note(
            title="Unicode Test",
            body="This has unicode: cafe, resume, naive, and more.",
        )
        assert result["ok"] is True
        note = tmp_vault.get_note(title="Unicode Test")
        assert "unicode" in note["body"]

    def test_wiki_link_in_tags_not_extracted(self):
        # Tags and wiki-links are different syntaxes
        tags = extract_tags("[[Not a Tag]]")
        assert len(tags) == 0

    def test_get_with_no_args_returns_none(self, tmp_vault):
        assert tmp_vault.get_note() is None

    def test_concurrent_note_ids_unique(self, tmp_vault):
        ids = set()
        for i in range(20):
            result = tmp_vault.create_note(title=f"Note {i}", body=f"Body {i}")
            ids.add(result["id"])
        assert len(ids) == 20
