#!/usr/bin/env python3
"""
Permanence OS — Migrate existing flat-file data to SQLite.

One-time migration script that reads:
  - memory/zero_point_store.json   → zero_point_entries table
  - memory/episodic/episodic_*.jsonl → episodic_log table
  - logs/model_calls.jsonl         → model_cost_log table
  - knowledge_graph/graph.json     → knowledge_nodes + knowledge_edges tables

Safe to re-run: uses INSERT OR REPLACE/IGNORE to avoid duplicates.

Usage:
    python scripts/migrate_to_sqlite.py [--db-path PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.synthesis_db import SynthesisDB
from core.cost_tracker import estimate_cost


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate_zero_point(db: SynthesisDB, base_dir: Path, dry_run: bool) -> int:
    """Migrate memory/zero_point_store.json → zero_point_entries."""
    store_path = base_dir / "memory" / "zero_point_store.json"
    if not store_path.exists():
        print(f"  ⏭  {store_path} not found — skipping")
        return 0

    try:
        with open(store_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  ⚠  Failed to read {store_path}: {exc}")
        return 0

    entries = data.get("entries", {})
    count = 0
    for entry_id, entry_data in entries.items():
        if dry_run:
            print(f"    [DRY-RUN] Would migrate ZP entry: {entry_id}")
            count += 1
            continue

        tags = entry_data.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        try:
            db.write_zero_point(
                entry_id=entry_data.get("entry_id", entry_id),
                memory_type=entry_data.get("memory_type", "FACT"),
                content=entry_data.get("content", ""),
                tags=tags,
                source=entry_data.get("source", "migration"),
                author_agent=entry_data.get("author_agent", "migration_script"),
                confidence=entry_data.get("confidence", "LOW"),
                evidence_count=int(entry_data.get("evidence_count", 1)),
                limitations=entry_data.get("limitations"),
                version=int(entry_data.get("version", 1)),
            )
            count += 1
        except Exception as exc:
            print(f"    ⚠  Failed to migrate ZP entry {entry_id}: {exc}")

    return count


def migrate_episodic(db: SynthesisDB, base_dir: Path, dry_run: bool) -> int:
    """Migrate memory/episodic/episodic_*.jsonl → episodic_log."""
    episodic_dir = base_dir / "memory" / "episodic"
    if not episodic_dir.exists():
        print(f"  ⏭  {episodic_dir} not found — skipping")
        return 0

    count = 0
    for jsonl_file in sorted(episodic_dir.glob("episodic_*.jsonl")):
        try:
            with open(jsonl_file) as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        print(f"    ⚠  Bad JSON in {jsonl_file.name}:{line_num}")
                        continue

                    if dry_run:
                        print(
                            f"    [DRY-RUN] Would migrate episodic: "
                            f"{entry.get('task_id', 'unknown')}"
                        )
                        count += 1
                        continue

                    inputs = entry.get("inputs", {})
                    outputs = entry.get("outputs", {})
                    governance = entry.get("governance", {})

                    try:
                        db.write_episodic(
                            task_id=entry.get("task_id", ""),
                            task_goal=inputs.get("goal", "")
                            if isinstance(inputs, dict)
                            else "",
                            stage=governance.get("stage", "")
                            if isinstance(governance, dict)
                            else "",
                            status="COMPLETED",
                            risk_tier=entry.get("risk_tier", "LOW"),
                            agents_involved=entry.get("agents_involved"),
                            inputs_json=json.dumps(inputs)
                            if isinstance(inputs, dict)
                            else str(inputs),
                            outputs_json=json.dumps(outputs)
                            if isinstance(outputs, dict)
                            else str(outputs),
                            duration_seconds=entry.get("duration_seconds"),
                        )
                        count += 1
                    except Exception as exc:
                        print(
                            f"    ⚠  Failed to migrate episodic "
                            f"{entry.get('task_id', '?')}: {exc}"
                        )
        except OSError as exc:
            print(f"    ⚠  Failed to read {jsonl_file}: {exc}")

    return count


def migrate_model_calls(db: SynthesisDB, base_dir: Path, dry_run: bool) -> int:
    """Migrate logs/model_calls.jsonl → model_cost_log."""
    log_path = base_dir / "logs" / "model_calls.jsonl"
    if not log_path.exists():
        print(f"  ⏭  {log_path} not found — skipping")
        return 0

    count = 0
    try:
        with open(log_path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    print(f"    ⚠  Bad JSON in model_calls.jsonl:{line_num}")
                    continue

                model_id = entry.get("model", "")
                provider = entry.get("provider", "")
                # Infer provider from model name if not present
                if not provider:
                    if "claude" in model_id:
                        provider = "anthropic"
                    elif "gpt" in model_id:
                        provider = "openai"
                    elif "grok" in model_id:
                        provider = "xai"
                    else:
                        provider = "unknown"

                input_tokens = int(entry.get("input_tokens", 0))
                output_tokens = int(entry.get("output_tokens", 0))
                cost = estimate_cost(model_id, provider, input_tokens, output_tokens)

                if dry_run:
                    print(
                        f"    [DRY-RUN] Would migrate cost log: "
                        f"{model_id} ${cost:.6f}"
                    )
                    count += 1
                    continue

                try:
                    db.log_cost(
                        model_id=model_id,
                        tier=entry.get("tier", ""),
                        provider=provider,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=cost,
                        session_id="migration",
                        task_id="",
                    )
                    count += 1
                except Exception as exc:
                    print(f"    ⚠  Failed to migrate cost log entry: {exc}")
    except OSError as exc:
        print(f"    ⚠  Failed to read {log_path}: {exc}")

    return count


def migrate_knowledge_graph(db: SynthesisDB, base_dir: Path, dry_run: bool) -> int:
    """Migrate knowledge_graph/graph.json → knowledge_nodes + knowledge_edges."""
    graph_path = base_dir / "knowledge_graph" / "graph.json"
    if not graph_path.exists():
        print(f"  ⏭  {graph_path} not found — skipping")
        return 0

    try:
        with open(graph_path) as f:
            graph = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  ⚠  Failed to read {graph_path}: {exc}")
        return 0

    count = 0

    # Nodes
    nodes = graph.get("nodes", [])
    if isinstance(nodes, dict):
        nodes = [{"id": k, **v} for k, v in nodes.items()]

    for node in nodes:
        node_id = node.get("id", node.get("node_id", ""))
        if not node_id:
            continue

        if dry_run:
            print(f"    [DRY-RUN] Would migrate node: {node_id}")
            count += 1
            continue

        metadata = {k: v for k, v in node.items() if k not in ("id", "node_id", "label", "type", "node_type")}
        try:
            db.write_knowledge_node(
                node_id=node_id,
                label=node.get("label", node_id),
                node_type=node.get("type", node.get("node_type", "")),
                metadata_json=json.dumps(metadata),
            )
            count += 1
        except Exception as exc:
            print(f"    ⚠  Failed to migrate node {node_id}: {exc}")

    # Edges
    edges = graph.get("edges", [])
    if isinstance(edges, dict):
        edges = list(edges.values()) if isinstance(list(edges.values())[0] if edges else {}, dict) else []

    for edge in edges:
        if not isinstance(edge, dict):
            continue

        source = edge.get("source", edge.get("source_id", ""))
        target = edge.get("target", edge.get("target_id", ""))
        relation = edge.get("relation", edge.get("label", "related"))

        if not source or not target:
            continue

        if dry_run:
            print(f"    [DRY-RUN] Would migrate edge: {source} → {target}")
            count += 1
            continue

        metadata = {
            k: v
            for k, v in edge.items()
            if k not in ("source", "source_id", "target", "target_id", "relation", "label", "weight")
        }
        try:
            db.write_knowledge_edge(
                source_id=source,
                target_id=target,
                relation=relation,
                weight=float(edge.get("weight", 1.0)),
                metadata_json=json.dumps(metadata),
            )
            count += 1
        except Exception as exc:
            print(f"    ⚠  Failed to migrate edge {source}→{target}: {exc}")

    return count


def main():
    parser = argparse.ArgumentParser(description="Migrate flat-file data to SQLite")
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to permanence.db (default: auto from storage)",
    )
    parser.add_argument(
        "--base-dir",
        default=str(PROJECT_ROOT),
        help="Project base directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    dry_run = args.dry_run

    print("")
    print("============================================")
    print("  Permanence OS — SQLite Migration")
    print("============================================")
    print(f"  Base dir:  {base_dir}")
    print(f"  DB path:   {args.db_path or 'auto'}")
    print(f"  Dry run:   {dry_run}")
    print("")

    db = SynthesisDB(db_path=args.db_path)

    print("==> Migrating Zero Point entries")
    zp_count = migrate_zero_point(db, base_dir, dry_run)
    print(f"    ✓ {zp_count} entries")

    print("")
    print("==> Migrating episodic log")
    ep_count = migrate_episodic(db, base_dir, dry_run)
    print(f"    ✓ {ep_count} entries")

    print("")
    print("==> Migrating model call costs")
    cost_count = migrate_model_calls(db, base_dir, dry_run)
    print(f"    ✓ {cost_count} entries")

    print("")
    print("==> Migrating knowledge graph")
    kg_count = migrate_knowledge_graph(db, base_dir, dry_run)
    print(f"    ✓ {kg_count} entries (nodes + edges)")

    print("")
    print("============================================")
    total = zp_count + ep_count + cost_count + kg_count
    action = "Would migrate" if dry_run else "Migrated"
    print(f"  {action}: {total} total entries")
    if not dry_run:
        stats = db.get_ledger_stats()
        print(f"  Ledger entries: {stats.get('total_entries', 0)}")
    print("============================================")
    print("")

    db.close()


if __name__ == "__main__":
    main()
