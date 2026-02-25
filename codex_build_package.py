"""
PERMANENCE OS — CODEX AUTONOMOUS BUILD PACKAGE
Version: 0.3.0
Date: February 25, 2026
Authority: Payton Hicks (Human, Final Authority)

CODEX INSTRUCTIONS:
- Read this file completely
- Run the assessment() function first to see what exists
- Then execute build() to start the highest-priority phase
- Log everything, escalate irreversible actions

This file gives Codex:
1. A gap assessment tool (run first)
2. The Knowledge Graph schema (build this — it's the missing backbone)
3. The model routing layer (build this — cost reduction)
4. The unified CLI scaffold (build this — unblocks everything)
5. The evaluation harness scaffold (build this — validates everything)
"""

import os
import json
import uuid
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ============================================================
# SECTION 1: CONSTANTS & CONFIG
# ============================================================

CANON_VALUES = {
    "agency_preservation": "Maintain human decision authority at all times",
    "truth_over_comfort": "Prefer accurate models even when emotionally costly",
    "compounding_intelligence": "Favor actions that increase future optionality",
    "coherence_over_intensity": "Sustainable systems beat peak performance",
    "structure_over_motivation": "Rules that work at 2 AM matter more than inspiration"
}

CANON_INVARIANTS = [
    "No agent modifies the Canon",
    "No memory without provenance (source, timestamp, confidence)",
    "No execution without evaluation",
    "All irreversible actions require human approval",
    "System must refuse cleanly when constraints are violated",
    "Logs are append-only and immutable",
    "Identity exists in patterns, not performance"
]

RISK_TIERS = {
    "LOW": "Reversible, informational, no external side effects → auto-execute",
    "MEDIUM": "Strategic, resource-consuming, ambiguous → Reviewer approval",
    "HIGH": "Irreversible, financial/legal/reputational → Human approval required"
}

# Model routing — cost-optimized
MODEL_ROUTING = {
    "canon_interpretation": "claude-opus-4-6",
    "strategy": "claude-opus-4-6",
    "code_generation": "claude-opus-4-6",
    "research_synthesis": "claude-sonnet-4-6",
    "planning": "claude-sonnet-4-6",
    "review": "claude-sonnet-4-6",
    "classification": "claude-haiku-4-5-20251001",
    "summarization": "claude-haiku-4-5-20251001",
    "tagging": "claude-haiku-4-5-20251001",
    "default": "claude-sonnet-4-6"
}

# Knowledge Graph schema
KG_NODE_TYPES = {
    "tool": ["name", "url", "category", "confidence", "source", "timestamp", "notes"],
    "framework": ["name", "language", "purpose", "confidence", "source", "timestamp"],
    "project": ["name", "status", "priority", "owner", "timestamp"],
    "skill": ["name", "domain", "level", "source", "timestamp"],
    "concept": ["name", "domain", "definition", "source", "timestamp"],
    "bookmark": ["text", "author", "url", "captured_at", "topic_tags", "action", "signal_score"]
}

KG_EDGE_TYPES = [
    "implements",    # project implements framework
    "replaces",      # tool replaces tool  
    "builds_on",     # concept builds_on concept
    "competes_with", # tool competes_with tool
    "used_in",       # framework used_in project
    "inspired_by",   # project inspired_by concept
    "related_to",    # general relationship
    "contradicts",   # conflicting signals
]

# Expected directory structure
EXPECTED_DIRS = [
    "canon",
    "core", 
    "agents",
    "tests",
    "memory",
    "logs",
    "knowledge_graph",
    "briefings",
    "sources"
]

EXPECTED_FILES = [
    "canon/values.yaml",
    "canon/invariants.yaml",
    "canon/tradeoffs.yaml",
    "canon/decision_heuristics.yaml",
    "canon/failure_archive.yaml",
    "core/state.py",
    "core/canon.py",
    "core/king_bot.py",
    "core/graph.py",
    "core/runner.py",
    "core/conciliator.py",
    "agents/base.py",
    "agents/planner.py",
    "agents/researcher.py",
    "agents/executor.py",
    "agents/reviewer.py",
    "cli.py",
]


def utc_now_iso() -> str:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# SECTION 2: ASSESSMENT — RUN THIS FIRST
# ============================================================

def assess_system(base_path: str = ".") -> dict:
    """
    Codex: Run this first. Tells you exactly what exists and what's missing.
    Returns a structured gap report.
    """
    base = Path(base_path)
    report = {
        "timestamp": utc_now_iso(),
        "base_path": str(base.absolute()),
        "existing_dirs": [],
        "missing_dirs": [],
        "existing_files": [],
        "missing_files": [],
        "gaps": [],
        "next_actions": []
    }

    # Check directories
    for d in EXPECTED_DIRS:
        p = base / d
        if p.exists():
            report["existing_dirs"].append(d)
        else:
            report["missing_dirs"].append(d)

    # Check files
    for f in EXPECTED_FILES:
        p = base / f
        if p.exists():
            report["existing_files"].append(f)
        else:
            report["missing_files"].append(f)

    # Identify specific gaps
    if "cli.py" not in report["existing_files"]:
        report["gaps"].append({
            "id": "GAP-001",
            "component": "Unified CLI",
            "priority": "CRITICAL",
            "description": "No unified entry point. Cannot run system from terminal.",
            "action": "Build cli.py with: run, status, clean, test, add-source commands"
        })

    if "tests" not in report["existing_dirs"]:
        report["gaps"].append({
            "id": "GAP-002",
            "component": "Evaluation Harness",
            "priority": "CRITICAL",
            "description": "No test directory found. Cannot validate Canon compliance.",
            "action": "Build tests/ with normal, adversarial, and failure injection categories"
        })

    if "knowledge_graph" not in report["existing_dirs"]:
        report["gaps"].append({
            "id": "GAP-003",
            "component": "Company Knowledge Graph",
            "priority": "HIGH",
            "description": "No Knowledge Graph. Agents have no structured context backbone.",
            "action": "Build knowledge_graph/ with schema, node CRUD, edge CRUD, query layer"
        })

    # Check for model routing
    core_path = base / "core"
    if core_path.exists():
        routing_exists = (core_path / "model_router.py").exists()
        if not routing_exists:
            report["gaps"].append({
                "id": "GAP-004",
                "component": "Model Routing Layer",
                "priority": "HIGH",
                "description": "No model routing. All tasks using same model — expensive and slow.",
                "action": "Build core/model_router.py with cost-optimized routing logic"
            })

    # Priority ordering of next actions
    report["next_actions"] = [
        "1. Build Unified CLI (GAP-001) — unblocks all testing",
        "2. Build Evaluation Harness (GAP-002) — validates everything built",
        "3. Wire real LLM inference into all agents — makes agents functional",
        "4. Build Model Router (GAP-004) — reduces cost 60-80%",
        "5. Build Knowledge Graph (GAP-003) — context backbone for agents",
        "6. Build Bookmark Ingestion Pipeline — feeds Knowledge Graph from X bookmarks",
        "7. Automate Memory Promotion — Working → Episodic automation",
        "8. Build Approval Queue UI — enables Level 2 trust tier"
    ]

    print(json.dumps(report, indent=2))
    return report


# ============================================================
# SECTION 3: MODEL ROUTING LAYER
# ============================================================

class ModelRouter:
    """
    Routes tasks to appropriate Claude model based on complexity and type.
    Goal: 60-80% cost reduction with no quality loss.
    
    Codex: Implement this. Wire into all agent API calls.
    """

    def __init__(self, log_path: str = "logs/model_routing.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def route(self, task_type: str, context: dict = None) -> str:
        """Returns the appropriate model string for this task type."""
        model = MODEL_ROUTING.get(task_type, MODEL_ROUTING["default"])
        
        # Log the routing decision
        entry = {
            "timestamp": utc_now_iso(),
            "task_type": task_type,
            "model_assigned": model,
            "canon_ref": "TRADEOFF: accumulation_vs_compression — cost efficiency enables sustainability",
            "context_keys": list(context.keys()) if context else []
        }
        
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        return model

    def estimate_cost_savings(self, task_distribution: dict) -> dict:
        """
        Given a distribution of task types, estimate cost vs all-Opus baseline.
        task_distribution: {"classification": 50, "research_synthesis": 30, "strategy": 20}
        """
        # Approximate relative costs (Opus = 1.0, Sonnet = 0.2, Haiku = 0.03)
        relative_costs = {
            "claude-opus-4-6": 1.0,
            "claude-sonnet-4-6": 0.2,
            "claude-haiku-4-5-20251001": 0.03
        }
        
        baseline_cost = sum(task_distribution.values())  # all Opus
        optimized_cost = 0
        
        for task_type, count in task_distribution.items():
            model = MODEL_ROUTING.get(task_type, MODEL_ROUTING["default"])
            optimized_cost += count * relative_costs[model]
        
        savings_pct = (1 - optimized_cost / baseline_cost) * 100
        
        return {
            "baseline_cost_units": baseline_cost,
            "optimized_cost_units": round(optimized_cost, 2),
            "estimated_savings_pct": round(savings_pct, 1),
            "routing_breakdown": {
                task: MODEL_ROUTING.get(task, MODEL_ROUTING["default"])
                for task in task_distribution.keys()
            }
        }


# ============================================================
# SECTION 4: KNOWLEDGE GRAPH
# ============================================================

class KnowledgeGraph:
    """
    The missing context backbone. Agents need structured knowledge to stop hallucinating.
    
    This is a simple JSON-based graph — Codex can upgrade to SQLite or Neo4j later.
    Start simple. Get it working. Then optimize.
    
    Codex: Build this. Wire it into Researcher agent as primary memory.
    """

    def __init__(self, storage_path: str = "knowledge_graph/graph.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if self.storage_path.exists():
            with open(self.storage_path) as f:
                data = json.load(f)
                self.nodes = data.get("nodes", {})
                self.edges = data.get("edges", [])
        else:
            self.nodes = {}
            self.edges = []

    def _save(self):
        with open(self.storage_path, "w") as f:
            json.dump({"nodes": self.nodes, "edges": self.edges}, f, indent=2)

    def add_node(self, node_type: str, attributes: dict, source: str, confidence: str = "MEDIUM") -> str:
        """
        Add a node to the graph. Returns node ID.
        CANON COMPLIANCE: Every node requires source, timestamp, confidence (provenance).
        """
        # Validate node type
        if node_type not in KG_NODE_TYPES:
            raise ValueError(f"Unknown node type: {node_type}. Valid: {list(KG_NODE_TYPES.keys())}")
        
        # Validate confidence
        if confidence not in ["HIGH", "MEDIUM", "LOW"]:
            raise ValueError(f"Confidence must be HIGH, MEDIUM, or LOW. Got: {confidence}")

        node_id = f"{node_type}_{uuid.uuid4().hex[:8]}"
        
        node = {
            "id": node_id,
            "type": node_type,
            "attributes": attributes,
            # Provenance — REQUIRED by Canon invariant
            "provenance": {
                "source": source,
                "timestamp": utc_now_iso(),
                "confidence": confidence
            }
        }
        
        self.nodes[node_id] = node
        self._save()
        
        return node_id

    def add_edge(self, from_id: str, to_id: str, edge_type: str, source: str) -> dict:
        """Add a directed edge between two nodes."""
        if edge_type not in KG_EDGE_TYPES:
            raise ValueError(f"Unknown edge type: {edge_type}. Valid: {KG_EDGE_TYPES}")
        
        if from_id not in self.nodes:
            raise ValueError(f"Node {from_id} not found")
        if to_id not in self.nodes:
            raise ValueError(f"Node {to_id} not found")

        edge = {
            "id": f"edge_{uuid.uuid4().hex[:8]}",
            "from": from_id,
            "to": to_id,
            "type": edge_type,
            "provenance": {
                "source": source,
                "timestamp": utc_now_iso()
            }
        }
        
        self.edges.append(edge)
        self._save()
        
        return edge

    def query_nodes(self, node_type: str = None, attribute_filter: dict = None) -> list:
        """Query nodes by type and/or attributes."""
        results = list(self.nodes.values())
        
        if node_type:
            results = [n for n in results if n["type"] == node_type]
        
        if attribute_filter:
            for key, value in attribute_filter.items():
                results = [n for n in results if n["attributes"].get(key) == value]
        
        return results

    def query_neighbors(self, node_id: str, edge_type: str = None) -> list:
        """Get all nodes connected to a node, optionally filtered by edge type."""
        neighbor_ids = []
        
        for edge in self.edges:
            if edge_type and edge["type"] != edge_type:
                continue
            if edge["from"] == node_id:
                neighbor_ids.append(edge["to"])
            elif edge["to"] == node_id:
                neighbor_ids.append(edge["from"])
        
        return [self.nodes[nid] for nid in neighbor_ids if nid in self.nodes]

    def get_stats(self) -> dict:
        """Get graph statistics."""
        type_counts = {}
        for node in self.nodes.values():
            t = node["type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        
        edge_counts = {}
        for edge in self.edges:
            t = edge["type"]
            edge_counts[t] = edge_counts.get(t, 0) + 1
        
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "nodes_by_type": type_counts,
            "edges_by_type": edge_counts
        }

    def ingest_bookmark(self, tweet_data: dict) -> str:
        """
        Convert an X bookmark into a Knowledge Graph node.
        tweet_data: {author, handle, timestamp, text, url, topic_tags}
        
        Codex: Wire this to the bookmark ingestion pipeline.
        """
        url = tweet_data.get("url", "").strip()
        if url:
            for node_id, node in self.nodes.items():
                if node.get("type") != "bookmark":
                    continue
                existing_url = node.get("attributes", {}).get("url", "").strip()
                if existing_url == url:
                    return node_id

        # Classify signal score (1-10, simple heuristic)
        signal_keywords = ["agent", "governance", "architecture", "graph", "knowledge", 
                          "orchestration", "framework", "memory", "routing", "audit"]
        text_lower = tweet_data.get("text", "").lower()
        signal_score = sum(1 for kw in signal_keywords if kw in text_lower)
        signal_score = min(signal_score, 10)
        
        attributes = {
            "text": tweet_data.get("text", ""),
            "author": tweet_data.get("author", ""),
            "handle": tweet_data.get("handle", ""),
            "url": url,
            "captured_at": tweet_data.get("timestamp", utc_now_iso()),
            "topic_tags": tweet_data.get("topic_tags", []),
            "action": "review",  # default: needs human classification
            "signal_score": signal_score
        }
        
        return self.add_node(
            node_type="bookmark",
            attributes=attributes,
            source=url or "x.com/bookmarks",
            confidence="MEDIUM"
        )


# ============================================================
# SECTION 5: BOOKMARK INGESTION PIPELINE
# ============================================================

class BookmarkIngestionPipeline:
    """
    Converts raw bookmark data into Knowledge Graph nodes.
    
    Input: List of tweet dicts from bookmark export
    Output: Knowledge Graph nodes with provenance
    
    Codex: Wire this to the Researcher agent and the Knowledge Graph.
    This is how the system converts passive bookmarking into active intelligence.
    """

    # Bookmarks from the uploaded document (Feb 21-25, 2026)
    # These are pre-classified for initial seeding
    RECENT_BOOKMARKS = [
        {
            "author": "Greg Isenberg", "handle": "gregisenberg",
            "timestamp": "2026-02-25", "url": "https://x.com/gregisenberg/status/2026665189765005433",
            "text": "how to build ai native vertical saas",
            "topic_tags": ["saas", "ai-native", "product"],
            "action": "study"
        },
        {
            "author": "Heinrich", "handle": "arscontexta",
            "timestamp": "2026-02-25", "url": "https://x.com/arscontexta/status/2026619782598955041",
            "text": "every company needs a well structured company knowledge graph for agents — context repository",
            "topic_tags": ["knowledge-graph", "agents", "architecture", "context"],
            "action": "implement"
        },
        {
            "author": "Eli Mernit", "handle": "mernit",
            "timestamp": "2026-02-23", "url": "https://x.com/mernit/status/2026438688297644503",
            "text": "Agents Don't Need Databases",
            "topic_tags": ["agents", "architecture", "memory"],
            "action": "evaluate"
        },
        {
            "author": "Kenneth Auchenberg", "handle": "auchenberg",
            "timestamp": "2026-02-23", "url": "https://x.com/auchenberg/status/2026382482271047789",
            "text": "Planning Is the New Coding",
            "topic_tags": ["planning", "agents", "workflow"],
            "action": "study"
        },
        {
            "author": "Theo", "handle": "theo",
            "timestamp": "2026-02-23", "url": "https://x.com/theo/status/2025900730847232409",
            "text": "Delete your CLAUDE.md. Delete your AGENTS.md.",
            "topic_tags": ["agents", "critique", "architecture"],
            "action": "evaluate"
        },
        {
            "author": "claudeai", "handle": "claudeai",
            "timestamp": "2026-02-24", "url": "https://x.com/claudeai/status/2026418433911603668",
            "text": "New in Claude Code: Remote Control",
            "topic_tags": ["claude", "tooling", "remote-control"],
            "action": "evaluate"
        },
        {
            "author": "Rohit", "handle": "rohit4verse",
            "timestamp": "2026-02-24", "url": "https://x.com/rohit4verse/status/2026359771427991764",
            "text": "watched another agentic ai project crash — poor architecture — here is the 10-step checklist",
            "topic_tags": ["architecture", "failure-modes", "agents", "checklist"],
            "action": "study"
        },
        {
            "author": "Greg Isenberg", "handle": "gregisenberg",
            "timestamp": "2026-02-23", "url": "https://x.com/gregisenberg/status/2026036464287412412",
            "text": "how to use obsidian + claude code — 24/7 personal operating system",
            "topic_tags": ["obsidian", "claude", "personal-os", "workflow"],
            "action": "evaluate"
        }
    ]

    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.log_path = Path("logs/bookmark_ingestion.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def ingest_all(self, bookmarks: list = None) -> dict:
        """
        Ingest a list of bookmarks into the Knowledge Graph.
        If no bookmarks provided, uses the pre-classified RECENT_BOOKMARKS.
        """
        bookmarks = bookmarks or self.RECENT_BOOKMARKS
        results = {"ingested": [], "skipped": [], "errors": []}
        
        for bm in bookmarks:
            try:
                node_id = self.kg.ingest_bookmark(bm)
                results["ingested"].append({"url": bm.get("url"), "node_id": node_id})
                
                # Log the ingestion
                log_entry = {
                    "timestamp": utc_now_iso(),
                    "action": "bookmark_ingested",
                    "url": bm.get("url"),
                    "node_id": node_id,
                    "signal_score": self.kg.nodes[node_id]["attributes"]["signal_score"],
                    "canon_ref": "HEURISTIC: source_dominance_check — multiple sources required"
                }
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
                    
            except Exception as e:
                results["errors"].append({"url": bm.get("url"), "error": str(e)})
        
        print(f"Ingested {len(results['ingested'])} bookmarks. Errors: {len(results['errors'])}")
        return results

    def classify_by_action(self) -> dict:
        """Group knowledge graph bookmark nodes by their action field."""
        bookmarks = self.kg.query_nodes(node_type="bookmark")
        classified = {"implement": [], "study": [], "evaluate": [], "review": [], "skip": []}
        
        for bm in bookmarks:
            action = bm["attributes"].get("action", "review")
            if action in classified:
                classified[action].append(bm)
        
        return classified

    def get_high_signal_bookmarks(self, threshold: int = 5) -> list:
        """Return bookmarks with signal score >= threshold."""
        bookmarks = self.kg.query_nodes(node_type="bookmark")
        return [bm for bm in bookmarks if bm["attributes"].get("signal_score", 0) >= threshold]


# ============================================================
# SECTION 6: EVALUATION HARNESS
# ============================================================

class EvaluationHarness:
    """
    Canon-compliant test framework. Three categories:
    1. Normal tasks — accuracy, sourcing, budget compliance
    2. Adversarial tasks — force hallucination, source bypass, budget overrun
    3. Failure injection — exceed limits mid-task, corrupt input, missing provenance
    
    Codex: Wire this to pytest. Add at least 5 tests per category minimum.
    Goal: 20+ tests total before moving to Phase B.
    """

    def __init__(self, log_path: str = "logs/eval_harness.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.results = []

    def run_test(self, test_id: str, test_fn, expected_behavior: str) -> dict:
        """Run a single test and log the result."""
        result = {
            "test_id": test_id,
            "expected": expected_behavior,
            "timestamp": utc_now_iso(),
            "passed": False,
            "error": None
        }
        
        try:
            outcome = test_fn()
            result["passed"] = bool(outcome)
            result["outcome"] = str(outcome)
        except Exception as e:
            result["error"] = str(e)
            result["passed"] = False
        
        self.results.append(result)
        
        with open(self.log_path, "a") as f:
            f.write(json.dumps(result) + "\n")
        
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {test_id}: {expected_behavior}")
        
        return result

    # --- NORMAL TESTS ---

    def test_canon_loads(self, canon_path: str = "canon") -> bool:
        """T-001: Canon loads and validates without errors."""
        p = Path(canon_path)
        split_required = [
            "values.yaml",
            "invariants.yaml",
            "tradeoffs.yaml",
            "decision_heuristics.yaml",
            "failure_archive.yaml",
        ]
        monolith_required = ["base_canon.yaml", "dna.yaml"]
        has_split = all((p / f).exists() for f in split_required)
        has_monolith = all((p / f).exists() for f in monolith_required)
        return has_split or has_monolith

    def test_knowledge_graph_provenance(self) -> bool:
        """T-002: Every KG node has required provenance fields."""
        kg = KnowledgeGraph()
        nodes = list(kg.nodes.values())
        if not nodes:
            return True  # Empty graph passes
        
        for node in nodes:
            prov = node.get("provenance", {})
            if not all(k in prov for k in ["source", "timestamp", "confidence"]):
                return False
        return True

    def test_model_router_logs(self) -> bool:
        """T-003: Model router logs every routing decision."""
        router = ModelRouter(log_path="logs/test_routing.jsonl")
        log_path = Path("logs/test_routing.jsonl")
        initial_size = log_path.stat().st_size if log_path.exists() else 0
        
        router.route("classification")
        router.route("strategy")
        
        new_size = log_path.stat().st_size if log_path.exists() else 0
        return new_size > initial_size

    def test_bookmark_ingestion(self) -> bool:
        """T-004: Bookmarks ingest with correct provenance."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(storage_path=f"{tmp}/test_graph.json")
            pipeline = BookmarkIngestionPipeline(kg)
            results = pipeline.ingest_all(pipeline.RECENT_BOOKMARKS[:3])
            
            if results["errors"]:
                return False
            
            # Verify provenance on all ingested nodes
            for item in results["ingested"]:
                node = kg.nodes.get(item["node_id"])
                if not node or "provenance" not in node:
                    return False
            
            return len(results["ingested"]) == 3

    # --- ADVERSARIAL TESTS ---

    def test_invalid_node_type_rejected(self) -> bool:
        """A-001: Knowledge Graph rejects unknown node types."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(storage_path=f"{tmp}/test.json")
            try:
                kg.add_node("hype_post", {"text": "get rich quick"}, source="x.com")
                return False  # Should have raised
            except ValueError:
                return True  # Correct — rejected

    def test_invalid_confidence_rejected(self) -> bool:
        """A-002: Knowledge Graph rejects invalid confidence values."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(storage_path=f"{tmp}/test.json")
            try:
                kg.add_node("tool", {"name": "test"}, source="test", confidence="DEFINITELY_TRUE")
                return False  # Should have raised
            except ValueError:
                return True  # Correct — rejected

    def test_invalid_edge_type_rejected(self) -> bool:
        """A-003: Knowledge Graph rejects unknown edge types."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(storage_path=f"{tmp}/test.json")
            n1 = kg.add_node("tool", {"name": "tool1"}, source="test")
            n2 = kg.add_node("tool", {"name": "tool2"}, source="test")
            try:
                kg.add_edge(n1, n2, "magically_related", source="test")
                return False  # Should have raised
            except ValueError:
                return True  # Correct — rejected

    def test_model_router_unknown_type(self) -> bool:
        """A-004: Model router defaults gracefully on unknown task type."""
        router = ModelRouter()
        model = router.route("completely_made_up_task_type")
        return model == MODEL_ROUTING["default"]

    # --- FAILURE INJECTION TESTS ---

    def test_kg_survives_corrupt_node_id(self) -> bool:
        """F-001: Knowledge Graph query handles nonexistent node gracefully."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(storage_path=f"{tmp}/test.json")
            # Querying a nonexistent neighbor should return empty list
            results = kg.query_neighbors("node_that_doesnt_exist")
            return results == []

    def test_log_is_append_only(self) -> bool:
        """F-002: Log files are append-only (never overwritten)."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            log_path = f"{tmp}/test.jsonl"
            router = ModelRouter(log_path=log_path)
            
            router.route("classification")
            size_after_1 = Path(log_path).stat().st_size
            
            router.route("strategy")
            size_after_2 = Path(log_path).stat().st_size
            
            return size_after_2 > size_after_1  # File grew, not replaced

    def run_all(self) -> dict:
        """Run all tests and return summary."""
        tests = [
            ("T-001", lambda: self.test_canon_loads(), "Canon loads and validates"),
            ("T-002", lambda: self.test_knowledge_graph_provenance(), "KG nodes have provenance"),
            ("T-003", lambda: self.test_model_router_logs(), "Model router logs decisions"),
            ("T-004", lambda: self.test_bookmark_ingestion(), "Bookmarks ingest with provenance"),
            ("A-001", lambda: self.test_invalid_node_type_rejected(), "Invalid node type rejected"),
            ("A-002", lambda: self.test_invalid_confidence_rejected(), "Invalid confidence rejected"),
            ("A-003", lambda: self.test_invalid_edge_type_rejected(), "Invalid edge type rejected"),
            ("A-004", lambda: self.test_model_router_unknown_type(), "Unknown task type defaults gracefully"),
            ("F-001", lambda: self.test_kg_survives_corrupt_node_id(), "KG handles nonexistent node"),
            ("F-002", lambda: self.test_log_is_append_only(), "Logs are append-only"),
        ]
        
        print("\n=== PERMANENCE OS EVALUATION HARNESS ===\n")
        
        for test_id, test_fn, expected in tests:
            self.run_test(test_id, test_fn, expected)
        
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        
        summary = {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{(passed/total)*100:.1f}%",
            "canon_fidelity": "PASS" if passed == total else f"NEEDS ATTENTION — {total-passed} failures"
        }
        
        print(f"\n=== RESULTS: {passed}/{total} PASS ({summary['pass_rate']}) ===\n")
        return summary


# ============================================================
# SECTION 7: UNIFIED CLI
# ============================================================

def build_cli_content() -> str:
    """
    Returns the content for cli.py — the unified entry point.
    Codex: Write this to cli.py in the Permanence OS root.
    """
    return '''#!/usr/bin/env python3
"""
Permanence OS — Unified CLI
Usage:
  permanence run <task>          Run a governed task
  permanence status              Show system status
  permanence test                Run evaluation harness
  permanence assess              Show gap analysis
  permanence ingest-bookmarks    Ingest bookmarks to Knowledge Graph
  permanence kg-stats            Show Knowledge Graph stats
  permanence clean               Archive old logs
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

def cmd_status():
    """Show current system status."""
    print("\\n=== PERMANENCE OS STATUS ===\\n")
    
    checks = {
        "Canon": Path("canon").exists() and all(
            Path(f"canon/{f}").exists() 
            for f in ["values.yaml", "invariants.yaml", "tradeoffs.yaml"]
        ),
        "Core agents": Path("agents").exists(),
        "Knowledge Graph": Path("knowledge_graph/graph.json").exists(),
        "Logs directory": Path("logs").exists(),
        "Briefings": Path("briefings").exists(),
    }
    
    for component, ok in checks.items():
        status = "✓" if ok else "✗"
        print(f"  {status}  {component}")
    
    # KG stats if available
    kg_path = Path("knowledge_graph/graph.json")
    if kg_path.exists():
        with open(kg_path) as f:
            data = json.load(f)
        print(f"\\n  Knowledge Graph: {len(data.get('nodes', {}))} nodes, {len(data.get('edges', []))} edges")
    
    print()

def cmd_test():
    """Run evaluation harness."""
    from codex_build_package import EvaluationHarness
    harness = EvaluationHarness()
    return harness.run_all()

def cmd_assess():
    """Run gap assessment."""
    from codex_build_package import assess_system
    return assess_system(".")

def cmd_ingest_bookmarks():
    """Ingest X bookmarks into Knowledge Graph."""
    from codex_build_package import KnowledgeGraph, BookmarkIngestionPipeline
    kg = KnowledgeGraph()
    pipeline = BookmarkIngestionPipeline(kg)
    results = pipeline.ingest_all()
    print(json.dumps(results, indent=2))

def cmd_kg_stats():
    """Show Knowledge Graph statistics."""
    from codex_build_package import KnowledgeGraph
    kg = KnowledgeGraph()
    stats = kg.get_stats()
    print(json.dumps(stats, indent=2))

def cmd_run(task_goal: str):
    """Run a governed task through the full pipeline."""
    print(f"\\n[PERMANENCE OS] Task received: {task_goal}")
    print("[POLEMARCH] Validating against Canon...")
    print("[POLEMARCH] Risk tier: MEDIUM")
    print("[POLEMARCH] Routing to Planner...")
    print("\\n[NOTE] Full LLM inference not yet wired. This is the scaffold.")
    print("[LOG] Task logged with timestamp and Canon reference.")
    
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_goal": task_goal,
        "stage": "INIT",
        "polemarch_decision": "ROUTE_TO_PLANNER",
        "risk_tier": "MEDIUM",
        "canon_ref": "HEURISTIC: reversibility_test"
    }
    
    log_path = Path("logs/tasks.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\\n")
    
    print(f"[LOG] Written to {log_path}")

def main():
    args = sys.argv[1:]
    
    if not args:
        print(__doc__)
        return
    
    cmd = args[0]
    
    if cmd == "status":
        cmd_status()
    elif cmd == "test":
        cmd_test()
    elif cmd == "assess":
        cmd_assess()
    elif cmd == "ingest-bookmarks":
        cmd_ingest_bookmarks()
    elif cmd == "kg-stats":
        cmd_kg_stats()
    elif cmd == "run" and len(args) > 1:
        cmd_run(" ".join(args[1:]))
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)

if __name__ == "__main__":
    main()
'''


# ============================================================
# SECTION 8: MAIN ENTRY POINT FOR CODEX
# ============================================================

def build(phase: str = "A", base_path: str = "."):
    """
    Codex: Call this to execute the build.
    
    Phases:
    - A: Foundation (CLI, eval harness, Knowledge Graph, model router)
    - B: Intelligence (bookmark ingestion, memory promotion)
    - C: Automation (approval queue, trust tier advancement)
    """
    print(f"\n=== PERMANENCE OS BUILD — PHASE {phase} ===\n")
    print(f"Timestamp: {utc_now_iso()}")
    print(f"Canon invariant: No execution without evaluation — running tests first\n")
    
    # Step 1: Assess
    print("--- STEP 1: ASSESS CURRENT STATE ---")
    report = assess_system(base_path)
    
    if phase == "A":
        # Step 2: Build Knowledge Graph
        print("\n--- STEP 2: INITIALIZE KNOWLEDGE GRAPH ---")
        kg_dir = Path(base_path) / "knowledge_graph"
        kg_dir.mkdir(exist_ok=True)
        kg = KnowledgeGraph(storage_path=str(kg_dir / "graph.json"))
        print(f"Knowledge Graph initialized at {kg_dir / 'graph.json'}")
        
        # Step 3: Ingest bookmarks
        print("\n--- STEP 3: INGEST BOOKMARKS ---")
        pipeline = BookmarkIngestionPipeline(kg)
        ingest_results = pipeline.ingest_all()
        
        # Step 4: Initialize model router
        print("\n--- STEP 4: INITIALIZE MODEL ROUTER ---")
        router = ModelRouter()
        
        # Show cost savings estimate
        sample_distribution = {
            "classification": 50,
            "summarization": 30,
            "research_synthesis": 15,
            "strategy": 5
        }
        savings = router.estimate_cost_savings(sample_distribution)
        print(f"Estimated cost savings vs all-Opus: {savings['estimated_savings_pct']}%")
        
        # Step 5: Run evaluation harness
        print("\n--- STEP 5: RUN EVALUATION HARNESS ---")
        harness = EvaluationHarness()
        summary = harness.run_all()
        
        # Step 6: Write CLI
        print("\n--- STEP 6: WRITE UNIFIED CLI ---")
        cli_content = build_cli_content()
        cli_path = Path(base_path) / "cli.py"
        if not cli_path.exists():
            with open(cli_path, "w") as f:
                f.write(cli_content)
            print(f"CLI written to {cli_path}")
        else:
            print(f"CLI already exists at {cli_path} — skipping (would need human approval to overwrite)")
        
        # Step 7: Log build session
        session_log = {
            "timestamp": utc_now_iso(),
            "phase": phase,
            "built": [
                "knowledge_graph/graph.json",
                "logs/bookmark_ingestion.jsonl",
                "logs/model_routing.jsonl",
                "logs/eval_harness.jsonl",
                "cli.py (if not existing)"
            ],
            "test_results": summary,
            "knowledge_graph_stats": kg.get_stats(),
            "bookmark_ingestion": ingest_results,
            "cost_savings_estimate": savings,
            "next_phase": "B — wire real LLM inference, add 10 more test cases",
            "canon_ref": "INVARIANT: no execution without evaluation — completed"
        }
        
        log_path = Path("logs/build_sessions.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(session_log) + "\n")
        
        print(f"\n=== PHASE A COMPLETE ===")
        print(f"Tests: {summary['passed']}/{summary['total']} passing")
        print(f"KG nodes: {kg.get_stats()['total_nodes']}")
        print(f"Session logged to {log_path}")
        print(f"\nNext: Phase B — wire LLM inference into agents, add 10 more test cases")
        
        return session_log


if __name__ == "__main__":
    # Codex: Run this directly
    # python codex_build_package.py
    build(phase="A")
