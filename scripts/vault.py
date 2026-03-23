#!/usr/bin/env python3
"""
PERMANENCE OS -- Knowledge Vault

Built-in note-taking system with wiki-links, backlinks, tags, search,
and daily notes. An Obsidian alternative native to the Intelligence surface.

Storage model (three layers, all kept in sync):
  1. Markdown files in permanence_storage/vault/ (human-readable, git-friendly)
  2. SQLite FTS5 index at permanence_storage/vault_index.db (fast search)
  3. Entity Graph nodes (type: NOTE) + LINKED_TO relationships (graph queries)

Design:
  - 60/30/10 rule: 90% deterministic file + SQLite ops, 10% rule-based
    parsing (wiki-link regex, tag extraction). Zero AI calls.
  - try/except on ALL file I/O and database operations
  - Graceful degradation if Entity Graph is unavailable
  - pathlib for all file operations
  - No emojis

Usage:
  python scripts/vault.py --action create --title "My Note" --body "Content here"
  python scripts/vault.py --action get --title "My Note"
  python scripts/vault.py --action search --query "search term"
  python scripts/vault.py --action daily
  python scripts/vault.py --action backlinks --title "My Note"
  python scripts/vault.py --action graph
  python scripts/vault.py --action tags
  python scripts/vault.py --action list --tag "project" --limit 20
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = Path(
    os.getenv("PERMANENCE_STORAGE_DIR", str(BASE_DIR / "permanence_storage"))
)
DEFAULT_VAULT_DIR = STORAGE_DIR / "vault"
DEFAULT_INDEX_DB = str(STORAGE_DIR / "vault_index.db")
DEFAULT_ENTITY_DB = str(STORAGE_DIR / "entity_graph.db")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Regex for [[Note Title]] and [[Note Title|Display Text]]
WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")

# Regex for #tag (supports hyphens and underscores, not pure numbers)
TAG_RE = re.compile(r"(?:^|(?<=\s))#([a-zA-Z][a-zA-Z0-9_-]*)")

DAILY_NOTE_TEMPLATE = """# {date}

## Tasks

- [ ]

## Notes



## Reflections


"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_id() -> str:
    """Generate a 12-character hex ID."""
    seed = _now_iso() + os.urandom(8).hex()
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _title_to_filename(title: str) -> str:
    """Convert a note title to a safe filename (preserving readability)."""
    # Replace characters that are problematic in filenames
    safe = title.strip()
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        safe = safe.replace(ch, '-')
    # Collapse multiple dashes/spaces
    safe = re.sub(r'[-\s]+', '-', safe).strip('-')
    if not safe:
        safe = "untitled"
    return safe + ".md"


def _filename_to_title(filename: str) -> str:
    """Extract title from a markdown filename."""
    return filename.rsplit(".md", 1)[0].replace("-", " ")


def extract_wiki_links(text: str) -> list[dict[str, str]]:
    """
    Extract all [[wiki-links]] from markdown text.

    Returns list of dicts with 'target' (note title) and 'display' (alias or title).
    """
    links = []
    for match in WIKI_LINK_RE.finditer(text):
        target = match.group(1).strip()
        display = (match.group(2) or target).strip()
        if target:
            links.append({"target": target, "display": display})
    return links


def extract_tags(text: str) -> list[str]:
    """
    Extract all #tags from markdown text.

    Supports multi-word tags with hyphens: #project-alpha
    Returns deduplicated list in order of first appearance.
    """
    seen = set()
    tags = []
    for match in TAG_RE.finditer(text):
        tag = match.group(1).lower()
        if tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


# ---------------------------------------------------------------------------
# Index database (FTS5)
# ---------------------------------------------------------------------------

_INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    filename TEXT NOT NULL UNIQUE,
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    entity_id TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_vault_title ON vault_notes(title);
CREATE INDEX IF NOT EXISTS idx_vault_updated ON vault_notes(updated_at);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(
    title, body, tags,
    content='',
    tokenize='porter'
);
"""


def _get_index_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open (or create) the vault index database."""
    path = db_path or DEFAULT_INDEX_DB
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_INDEX_SCHEMA)
    # Try creating FTS table (may already exist)
    try:
        conn.executescript(_FTS_SCHEMA)
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Entity Graph integration (graceful degradation)
# ---------------------------------------------------------------------------

def _get_entity_graph(db_path: Optional[str] = None):
    """
    Try to import and instantiate EntityGraph. Returns None on failure.
    """
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR / "core"))
        from entity_graph import EntityGraph
        eg_path = db_path or DEFAULT_ENTITY_DB
        return EntityGraph(db_path=eg_path)
    except Exception:
        return None


def _sync_to_entity_graph(
    note_id: str,
    title: str,
    tags: list[str],
    wiki_links: list[dict[str, str]],
    entity_db_path: Optional[str] = None,
) -> Optional[str]:
    """
    Create or update a NOTE entity in the Entity Graph.
    Returns the entity_id or None if Entity Graph is unavailable.
    """
    eg = _get_entity_graph(entity_db_path)
    if eg is None:
        return None

    try:
        # Check if entity already exists for this vault note
        existing = eg.search(title, entity_type="NOTE", limit=1)
        entity_id = None
        for ent in existing:
            if ent.get("title") == title:
                entity_id = ent["id"]
                break

        props = {"vault_note_id": note_id, "tags": tags}

        if entity_id:
            eg.update_entity(entity_id, {
                "title": title,
                "properties": props,
            })
        else:
            result = eg.create_entity(
                entity_type="NOTE",
                title=title,
                properties=props,
                created_by="vault",
            )
            entity_id = result["id"]

        # Sync wiki-link relationships
        # First remove old LINKED_TO from this entity
        try:
            conn = eg._connect()
            conn.execute(
                "DELETE FROM relationships WHERE source_id = ? AND relationship = 'LINKED_TO'",
                (entity_id,),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

        # Create LINKED_TO for each wiki-link target
        for link in wiki_links:
            target_title = link["target"]
            targets = eg.search(target_title, entity_type="NOTE", limit=1)
            target_id = None
            for t in targets:
                if t.get("title") == target_title:
                    target_id = t["id"]
                    break
            if target_id and target_id != entity_id:
                try:
                    eg.link(entity_id, target_id, "LINKED_TO")
                except Exception:
                    pass

        return entity_id
    except Exception:
        return None


def _remove_from_entity_graph(
    title: str,
    entity_db_path: Optional[str] = None,
) -> bool:
    """Remove a NOTE entity from the Entity Graph."""
    eg = _get_entity_graph(entity_db_path)
    if eg is None:
        return False
    try:
        existing = eg.search(title, entity_type="NOTE", limit=1)
        for ent in existing:
            if ent.get("title") == title:
                eg.delete_entity(ent["id"])
                return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------

class Vault:
    """Knowledge Vault -- markdown notes with wiki-links, tags, and search."""

    def __init__(
        self,
        vault_dir: Optional[str] = None,
        index_db_path: Optional[str] = None,
        entity_db_path: Optional[str] = None,
    ):
        self.vault_dir = Path(vault_dir) if vault_dir else DEFAULT_VAULT_DIR
        self.index_db_path = index_db_path or DEFAULT_INDEX_DB
        self.entity_db_path = entity_db_path
        self._ensure_vault_dir()

    def _ensure_vault_dir(self) -> None:
        """Create the vault directory if it does not exist."""
        try:
            self.vault_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Failed to create vault directory: {e}")

    def _index_conn(self) -> sqlite3.Connection:
        """Get a connection to the index database."""
        return _get_index_db(self.index_db_path)

    # -- Create ------------------------------------------------------------

    def create_note(
        self,
        title: str,
        body: str = "",
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Create a new note.

        Args:
            title: Note title (must be unique)
            body: Markdown body content
            tags: Optional list of tags (also extracted from body)

        Returns:
            Dict with ok, id, title, filename, tags, wiki_links.
        """
        if not title or not title.strip():
            return {"ok": False, "error": "Title cannot be empty"}

        title = title.strip()
        filename = _title_to_filename(title)
        filepath = self.vault_dir / filename

        # Check for duplicate
        if filepath.exists():
            return {"ok": False, "error": f"Note already exists: {title}"}

        note_id = _generate_id()
        now = _now_iso()

        # Extract tags from body and merge with explicit tags
        body_tags = extract_tags(body) if body else []
        all_tags = list(dict.fromkeys((tags or []) + body_tags))

        # Extract wiki-links
        wiki_links = extract_wiki_links(body) if body else []

        # Build the markdown content with frontmatter
        frontmatter = (
            f"---\n"
            f"id: {note_id}\n"
            f"title: {title}\n"
            f"tags: {json.dumps(all_tags)}\n"
            f"created_at: {now}\n"
            f"updated_at: {now}\n"
            f"---\n\n"
        )
        full_content = frontmatter + (body or "")

        # Write file
        try:
            filepath.write_text(full_content, encoding="utf-8")
        except OSError as e:
            return {"ok": False, "error": f"Failed to write file: {e}"}

        # Index in SQLite
        conn = self._index_conn()
        try:
            conn.execute(
                """INSERT INTO vault_notes (id, title, filename, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (note_id, title, filename, json.dumps(all_tags), now, now),
            )
            # FTS index
            try:
                conn.execute(
                    "INSERT INTO vault_fts (rowid, title, body, tags) VALUES (?, ?, ?, ?)",
                    (conn.execute("SELECT last_insert_rowid()").fetchone()[0],
                     title, body or "", " ".join(all_tags)),
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()
        except sqlite3.Error as e:
            return {"ok": False, "error": f"Index error: {e}"}

        # Sync to Entity Graph
        entity_id = _sync_to_entity_graph(
            note_id, title, all_tags, wiki_links,
            entity_db_path=self.entity_db_path,
        )
        if entity_id:
            try:
                conn.execute(
                    "UPDATE vault_notes SET entity_id = ? WHERE id = ?",
                    (entity_id, note_id),
                )
                conn.commit()
            except sqlite3.Error:
                pass

        return {
            "ok": True,
            "id": note_id,
            "title": title,
            "filename": filename,
            "tags": all_tags,
            "wiki_links": wiki_links,
            "entity_id": entity_id,
        }

    # -- Read --------------------------------------------------------------

    def get_note(
        self, title: Optional[str] = None, note_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Get a note by title or ID.

        Returns dict with id, title, filename, body, tags, wiki_links,
        created_at, updated_at. Returns None if not found.
        """
        conn = self._index_conn()

        try:
            if note_id:
                row = conn.execute(
                    "SELECT * FROM vault_notes WHERE id = ?", (note_id,)
                ).fetchone()
            elif title:
                row = conn.execute(
                    "SELECT * FROM vault_notes WHERE title = ?", (title.strip(),)
                ).fetchone()
            else:
                return None
        except sqlite3.Error:
            return None

        if row is None:
            return None

        filename = row["filename"]
        filepath = self.vault_dir / filename

        body = ""
        try:
            raw = filepath.read_text(encoding="utf-8")
            # Strip frontmatter
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    body = parts[2].strip()
                else:
                    body = raw
            else:
                body = raw
        except OSError:
            pass

        tags = []
        try:
            tags = json.loads(row["tags"] or "[]")
        except (json.JSONDecodeError, TypeError):
            pass

        return {
            "id": row["id"],
            "title": row["title"],
            "filename": filename,
            "body": body,
            "tags": tags,
            "wiki_links": extract_wiki_links(body),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "entity_id": row["entity_id"] or "",
        }

    # -- Update ------------------------------------------------------------

    def update_note(
        self,
        title: str,
        body: Optional[str] = None,
        new_title: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Update an existing note.

        Args:
            title: Current title of the note
            body: New body content (None = keep existing)
            new_title: Rename the note (None = keep existing)
            tags: Explicit tags to set (also merges body tags)

        Returns:
            Dict with ok and updated fields.
        """
        note = self.get_note(title=title)
        if note is None:
            return {"ok": False, "error": f"Note not found: {title}"}

        effective_title = (new_title.strip() if new_title else title).strip()
        effective_body = body if body is not None else note["body"]

        # Extract tags
        body_tags = extract_tags(effective_body)
        all_tags = list(dict.fromkeys((tags if tags is not None else note["tags"]) + body_tags))

        wiki_links = extract_wiki_links(effective_body)
        now = _now_iso()

        # If title changed, rename the file
        old_filename = note["filename"]
        new_filename = _title_to_filename(effective_title)
        old_path = self.vault_dir / old_filename
        new_path = self.vault_dir / new_filename

        if new_title and new_title.strip() != title.strip():
            if new_path.exists() and new_path != old_path:
                return {"ok": False, "error": f"Note already exists: {effective_title}"}
            try:
                if old_path.exists():
                    old_path.rename(new_path)
            except OSError as e:
                return {"ok": False, "error": f"Failed to rename file: {e}"}

        # Write updated content
        frontmatter = (
            f"---\n"
            f"id: {note['id']}\n"
            f"title: {effective_title}\n"
            f"tags: {json.dumps(all_tags)}\n"
            f"created_at: {note['created_at']}\n"
            f"updated_at: {now}\n"
            f"---\n\n"
        )
        target_path = new_path if (new_title and new_title.strip() != title.strip()) else (self.vault_dir / old_filename)
        try:
            target_path.write_text(frontmatter + effective_body, encoding="utf-8")
        except OSError as e:
            return {"ok": False, "error": f"Failed to write file: {e}"}

        # Update index
        conn = self._index_conn()
        try:
            conn.execute(
                """UPDATE vault_notes
                   SET title = ?, filename = ?, tags = ?, updated_at = ?
                   WHERE id = ?""",
                (effective_title, target_path.name, json.dumps(all_tags), now, note["id"]),
            )
            conn.commit()
        except sqlite3.Error as e:
            return {"ok": False, "error": f"Index error: {e}"}

        # Sync to Entity Graph
        _sync_to_entity_graph(
            note["id"], effective_title, all_tags, wiki_links,
            entity_db_path=self.entity_db_path,
        )

        return {
            "ok": True,
            "id": note["id"],
            "title": effective_title,
            "filename": target_path.name,
            "tags": all_tags,
            "wiki_links": wiki_links,
        }

    # -- Delete ------------------------------------------------------------

    def delete_note(self, title: str) -> dict[str, Any]:
        """
        Delete a note by title.

        Removes the markdown file, index entry, and Entity Graph node.
        """
        note = self.get_note(title=title)
        if note is None:
            return {"ok": False, "error": f"Note not found: {title}"}

        # Remove file
        filepath = self.vault_dir / note["filename"]
        try:
            if filepath.exists():
                filepath.unlink()
        except OSError as e:
            return {"ok": False, "error": f"Failed to delete file: {e}"}

        # Remove from index
        conn = self._index_conn()
        try:
            conn.execute("DELETE FROM vault_notes WHERE id = ?", (note["id"],))
            conn.commit()
        except sqlite3.Error:
            pass

        # Remove from Entity Graph
        _remove_from_entity_graph(title, entity_db_path=self.entity_db_path)

        return {"ok": True, "id": note["id"], "title": title}

    # -- Backlinks ---------------------------------------------------------

    def get_backlinks(self, title: str) -> list[dict[str, Any]]:
        """
        Find all notes that link TO the given note via [[wiki-links]].

        Returns list of dicts with: id, title, context (surrounding text).
        """
        if not title or not title.strip():
            return []

        target_title = title.strip()
        backlinks = []

        conn = self._index_conn()
        try:
            rows = conn.execute("SELECT id, title, filename FROM vault_notes").fetchall()
        except sqlite3.Error:
            return []

        for row in rows:
            if row["title"] == target_title:
                continue
            filepath = self.vault_dir / row["filename"]
            try:
                raw = filepath.read_text(encoding="utf-8")
            except OSError:
                continue

            # Strip frontmatter for body
            body = raw
            if raw.startswith("---"):
                parts = raw.split("---", 2)
                if len(parts) >= 3:
                    body = parts[2]

            links = extract_wiki_links(body)
            for link in links:
                if link["target"] == target_title:
                    # Extract context: find the line containing the link
                    context = ""
                    for line in body.split("\n"):
                        if f"[[{target_title}" in line:
                            context = line.strip()[:200]
                            break
                    backlinks.append({
                        "id": row["id"],
                        "title": row["title"],
                        "context": context,
                    })
                    break  # One backlink entry per note

        return backlinks

    # -- Daily notes -------------------------------------------------------

    def create_daily_note(
        self, date: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create (or return) today's daily note.

        Args:
            date: Optional date string (YYYY-MM-DD). Defaults to today.

        Returns:
            Dict with ok, id, title, filename, is_new.
        """
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                return {"ok": False, "error": f"Invalid date format: {date}. Use YYYY-MM-DD"}
        else:
            target_date = datetime.now(timezone.utc).date()

        date_str = target_date.strftime("%Y-%m-%d")
        title = date_str

        # Check if it already exists
        existing = self.get_note(title=title)
        if existing:
            return {
                "ok": True,
                "id": existing["id"],
                "title": title,
                "filename": existing["filename"],
                "is_new": False,
            }

        # Build body with previous day link
        prev_date = target_date - timedelta(days=1)
        prev_str = prev_date.strftime("%Y-%m-%d")
        body = DAILY_NOTE_TEMPLATE.format(date=date_str)
        body += f"\n---\nPrevious: [[{prev_str}]]\n"

        result = self.create_note(
            title=title,
            body=body,
            tags=["daily"],
        )
        if result.get("ok"):
            result["is_new"] = True
        return result

    # -- Search ------------------------------------------------------------

    def search(
        self,
        query: str,
        tag: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Full-text search across vault notes.

        Searches title, body, and tags. Supports additional filters.
        """
        if not query and not tag:
            return []

        conn = self._index_conn()
        results = []

        # Try FTS5 first for text queries
        if query and query.strip():
            try:
                fts_rows = conn.execute(
                    """SELECT rowid, title, body, tags FROM vault_fts
                       WHERE vault_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (query.strip(), limit * 2),
                ).fetchall()

                matched_titles = set()
                for frow in fts_rows:
                    matched_titles.add(frow["title"])

                for t in matched_titles:
                    note = self.get_note(title=t)
                    if note:
                        results.append(note)
                    if len(results) >= limit:
                        break

                if results:
                    return self._apply_filters(results, tag, date_from, date_to, limit)
            except sqlite3.OperationalError:
                pass

        # LIKE fallback
        if query and query.strip():
            search_term = f"%{query.strip()}%"
            try:
                rows = conn.execute(
                    """SELECT id, title, filename FROM vault_notes
                       WHERE title LIKE ? OR tags LIKE ?
                       ORDER BY updated_at DESC
                       LIMIT ?""",
                    (search_term, search_term, limit * 2),
                ).fetchall()
            except sqlite3.Error:
                rows = []

            seen = {r["id"] for r in results}
            for row in rows:
                if row["id"] in seen:
                    continue
                note = self.get_note(title=row["title"])
                if note:
                    results.append(note)

            # Also search file contents
            try:
                for md_file in sorted(self.vault_dir.glob("*.md")):
                    try:
                        content = md_file.read_text(encoding="utf-8")
                        if query.strip().lower() in content.lower():
                            file_title = _filename_to_title(md_file.name)
                            note = self.get_note(title=file_title)
                            if note and note["id"] not in seen:
                                seen.add(note["id"])
                                results.append(note)
                    except OSError:
                        continue
            except OSError:
                pass

        # Tag-only search
        if tag and not query:
            tag_lower = tag.strip().lower()
            try:
                rows = conn.execute(
                    "SELECT id, title FROM vault_notes ORDER BY updated_at DESC"
                ).fetchall()
                for row in rows:
                    note = self.get_note(title=row["title"])
                    if note and tag_lower in [t.lower() for t in note.get("tags", [])]:
                        results.append(note)
                    if len(results) >= limit:
                        break
            except sqlite3.Error:
                pass

        return self._apply_filters(results, tag if query else None, date_from, date_to, limit)

    def _apply_filters(
        self,
        results: list[dict[str, Any]],
        tag: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Apply tag and date range filters to search results."""
        filtered = results

        if tag:
            tag_lower = tag.strip().lower()
            filtered = [
                r for r in filtered
                if tag_lower in [t.lower() for t in r.get("tags", [])]
            ]

        if date_from:
            filtered = [
                r for r in filtered
                if r.get("created_at", "") >= date_from
            ]

        if date_to:
            filtered = [
                r for r in filtered
                if r.get("created_at", "") <= date_to + "T23:59:59"
            ]

        return filtered[:limit]

    # -- List notes --------------------------------------------------------

    def list_notes(
        self,
        tag: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List all notes, optionally filtered by tag."""
        conn = self._index_conn()
        try:
            rows = conn.execute(
                "SELECT id, title, filename, tags, created_at, updated_at FROM vault_notes ORDER BY updated_at DESC LIMIT ?",
                (limit * 2,),
            ).fetchall()
        except sqlite3.Error:
            return []

        results = []
        for row in rows:
            tags_list = []
            try:
                tags_list = json.loads(row["tags"] or "[]")
            except (json.JSONDecodeError, TypeError):
                pass

            if tag:
                if tag.strip().lower() not in [t.lower() for t in tags_list]:
                    continue

            results.append({
                "id": row["id"],
                "title": row["title"],
                "filename": row["filename"],
                "tags": tags_list,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })
            if len(results) >= limit:
                break

        return results

    # -- Tags --------------------------------------------------------------

    def list_tags(self) -> dict[str, int]:
        """
        List all tags across the vault with counts.

        Returns dict mapping tag name to count of notes using it.
        """
        conn = self._index_conn()
        tag_counts: dict[str, int] = {}

        try:
            rows = conn.execute("SELECT tags FROM vault_notes").fetchall()
            for row in rows:
                try:
                    tags = json.loads(row["tags"] or "[]")
                except (json.JSONDecodeError, TypeError):
                    continue
                for tag in tags:
                    tag_lower = tag.lower()
                    tag_counts[tag_lower] = tag_counts.get(tag_lower, 0) + 1
        except sqlite3.Error:
            pass

        return dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True))

    # -- Graph export ------------------------------------------------------

    def export_graph(self) -> dict[str, Any]:
        """
        Export the note connection graph as JSON.

        Returns:
            Dict with 'nodes' (list) and 'edges' (list).
            Nodes: {id, title, tags, created_at}
            Edges: {source, target, source_title, target_title}
        """
        conn = self._index_conn()
        nodes = []
        edges = []
        title_to_id: dict[str, str] = {}

        try:
            rows = conn.execute(
                "SELECT id, title, tags, created_at, updated_at FROM vault_notes ORDER BY updated_at DESC"
            ).fetchall()
        except sqlite3.Error:
            return {"nodes": [], "edges": []}

        for row in rows:
            tags = []
            try:
                tags = json.loads(row["tags"] or "[]")
            except (json.JSONDecodeError, TypeError):
                pass

            nodes.append({
                "id": row["id"],
                "title": row["title"],
                "tags": tags,
                "created_at": row["created_at"],
            })
            title_to_id[row["title"]] = row["id"]

        # Scan files for wiki-links to build edges
        for node in nodes:
            note = self.get_note(title=node["title"])
            if not note:
                continue
            for link in note.get("wiki_links", []):
                target_title = link["target"]
                if target_title in title_to_id:
                    edges.append({
                        "source": node["id"],
                        "target": title_to_id[target_title],
                        "source_title": node["title"],
                        "target_title": target_title,
                    })

        return {"nodes": nodes, "edges": edges}

    # -- Reindex -----------------------------------------------------------

    def reindex(self) -> dict[str, Any]:
        """
        Rebuild the index from vault files on disk.

        Useful after manual edits to markdown files.
        """
        conn = self._index_conn()
        try:
            conn.execute("DELETE FROM vault_notes")
            try:
                conn.execute("DELETE FROM vault_fts")
            except sqlite3.OperationalError:
                pass
            conn.commit()
        except sqlite3.Error as e:
            return {"ok": False, "error": f"Failed to clear index: {e}"}

        indexed = 0
        errors = 0

        try:
            for md_file in sorted(self.vault_dir.glob("*.md")):
                try:
                    raw = md_file.read_text(encoding="utf-8")
                except OSError:
                    errors += 1
                    continue

                # Parse frontmatter
                note_id = _generate_id()
                title = _filename_to_title(md_file.name)
                tags: list[str] = []
                created_at = _now_iso()
                updated_at = _now_iso()
                body = raw

                if raw.startswith("---"):
                    parts = raw.split("---", 2)
                    if len(parts) >= 3:
                        fm = parts[1]
                        body = parts[2].strip()
                        for line in fm.split("\n"):
                            line = line.strip()
                            if line.startswith("id:"):
                                note_id = line.split(":", 1)[1].strip()
                            elif line.startswith("title:"):
                                title = line.split(":", 1)[1].strip()
                            elif line.startswith("tags:"):
                                try:
                                    tags = json.loads(line.split(":", 1)[1].strip())
                                except (json.JSONDecodeError, TypeError):
                                    pass
                            elif line.startswith("created_at:"):
                                created_at = line.split(":", 1)[1].strip()
                            elif line.startswith("updated_at:"):
                                updated_at = line.split(":", 1)[1].strip()

                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO vault_notes
                           (id, title, filename, tags, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (note_id, title, md_file.name, json.dumps(tags),
                         created_at, updated_at),
                    )
                    indexed += 1
                except sqlite3.Error:
                    errors += 1

            conn.commit()
        except OSError as e:
            return {"ok": False, "error": f"Failed to scan vault: {e}"}

        return {"ok": True, "indexed": indexed, "errors": errors}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Permanence OS -- Knowledge Vault"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=[
            "create", "get", "update", "delete",
            "search", "daily", "backlinks",
            "graph", "tags", "list", "reindex",
        ],
        help="Action to perform",
    )
    parser.add_argument("--title", default="", help="Note title")
    parser.add_argument("--body", default="", help="Note body (markdown)")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--new-title", default="", help="New title for rename")
    parser.add_argument("--id", dest="note_id", default="", help="Note ID")
    parser.add_argument("--query", default="", help="Search query")
    parser.add_argument("--tag", default="", help="Filter by tag")
    parser.add_argument("--date", default="", help="Date for daily note (YYYY-MM-DD)")
    parser.add_argument("--date-from", default="", help="Date range start")
    parser.add_argument("--date-to", default="", help="Date range end")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--vault-dir", default=None, help="Override vault directory")
    parser.add_argument("--index-db", default=None, help="Override index database path")
    parser.add_argument("--entity-db", default=None, help="Override entity graph database path")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    vault = Vault(
        vault_dir=args.vault_dir,
        index_db_path=args.index_db,
        entity_db_path=args.entity_db,
    )

    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None

    if args.action == "create":
        if not args.title:
            print("Error: --title is required for create")
            return 1
        result = vault.create_note(
            title=args.title,
            body=args.body,
            tags=tags_list,
        )
        if result["ok"]:
            print(f"Created: {result['title']}")
            print(f"  ID: {result['id']}")
            print(f"  File: {result['filename']}")
            if result["tags"]:
                print(f"  Tags: {', '.join(result['tags'])}")
            if result["wiki_links"]:
                print(f"  Links: {', '.join(l['target'] for l in result['wiki_links'])}")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    if args.action == "get":
        note = vault.get_note(
            title=args.title or None,
            note_id=args.note_id or None,
        )
        if note:
            print(json.dumps(note, indent=2))
        else:
            print("Note not found")
            return 1
        return 0

    if args.action == "update":
        if not args.title:
            print("Error: --title is required for update")
            return 1
        result = vault.update_note(
            title=args.title,
            body=args.body or None,
            new_title=args.new_title or None,
            tags=tags_list,
        )
        if result["ok"]:
            print(f"Updated: {result['title']}")
            print(f"  Tags: {', '.join(result.get('tags', []))}")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    if args.action == "delete":
        if not args.title:
            print("Error: --title is required for delete")
            return 1
        result = vault.delete_note(title=args.title)
        if result["ok"]:
            print(f"Deleted: {result['title']}")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    if args.action == "search":
        if not args.query and not args.tag:
            print("Error: --query or --tag is required for search")
            return 1
        results = vault.search(
            query=args.query,
            tag=args.tag or None,
            date_from=args.date_from or None,
            date_to=args.date_to or None,
            limit=args.limit,
        )
        if not results:
            print("No results found.")
        else:
            print(f"Search results ({len(results)}):")
            for note in results:
                tags_str = ", ".join(note.get("tags", []))
                print(f"  [{note['id']}] {note['title']}")
                if tags_str:
                    print(f"    Tags: {tags_str}")
        return 0

    if args.action == "daily":
        result = vault.create_daily_note(date=args.date or None)
        if result.get("ok"):
            status = "Created" if result.get("is_new") else "Already exists"
            print(f"{status}: {result['title']}")
            print(f"  File: {result['filename']}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            return 1
        return 0

    if args.action == "backlinks":
        if not args.title:
            print("Error: --title is required for backlinks")
            return 1
        backlinks = vault.get_backlinks(title=args.title)
        if not backlinks:
            print(f"No backlinks found for: {args.title}")
        else:
            print(f"Backlinks to '{args.title}' ({len(backlinks)}):")
            for bl in backlinks:
                print(f"  [{bl['id']}] {bl['title']}")
                if bl.get("context"):
                    print(f"    Context: {bl['context'][:100]}")
        return 0

    if args.action == "graph":
        graph = vault.export_graph()
        print(json.dumps(graph, indent=2))
        return 0

    if args.action == "tags":
        tag_counts = vault.list_tags()
        if not tag_counts:
            print("No tags found.")
        else:
            print(f"Tags ({len(tag_counts)}):")
            for tag, count in tag_counts.items():
                print(f"  #{tag}: {count}")
        return 0

    if args.action == "list":
        notes = vault.list_notes(tag=args.tag or None, limit=args.limit)
        if not notes:
            print("No notes found.")
        else:
            print(f"Notes ({len(notes)}):")
            for note in notes:
                tags_str = ", ".join(note.get("tags", []))
                line = f"  [{note['id']}] {note['title']}"
                if tags_str:
                    line += f" ({tags_str})"
                print(line)
        return 0

    if args.action == "reindex":
        result = vault.reindex()
        if result["ok"]:
            print(f"Reindexed: {result['indexed']} notes, {result['errors']} errors")
        else:
            print(f"Error: {result['error']}")
            return 1
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
