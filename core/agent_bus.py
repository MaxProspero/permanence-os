"""
Permanence OS -- Agent Bus (v1.0)

The central nervous system that gives every agent access to the Entity Graph,
all surface data, the Inbox overlay, persistent memory, and an event system.

Design:
  - Singleton pattern: one bus per process, thread-safe
  - 60/30/10 rule: deterministic ops, rule-based autonomy enforcement,
    AI reserved for future semantic search upgrades
  - All agent actions logged as Entity Graph nodes (type: AGENT_ACTION)
  - Approval gates enforced by autonomy level -- human authority is final
  - Graceful degradation if any subsystem is unavailable

Autonomy levels:
  FULL_AUTO       -- agent can act without approval
  SOFT_APPROVAL   -- agent acts, but flags for review within 30 min
  EXPLICIT_APPROVAL -- agent must wait for human approval
  NEVER           -- agent cannot take this class of action at all

Usage:
    from core.agent_bus import get_bus
    bus = get_bus()
    bus.register("sentinel", ["governance", "compliance"], "EXPLICIT_APPROVAL")
    bus.graph.create_entity("TASK", "Review PR", created_by="sentinel")
    bus.inbox_push({"title": "New approval needed", "source": "sentinel"})
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class AutonomyLevel(Enum):
    """How much freedom an agent has to act without human approval."""
    FULL_AUTO = "FULL_AUTO"
    SOFT_APPROVAL = "SOFT_APPROVAL"
    EXPLICIT_APPROVAL = "EXPLICIT_APPROVAL"
    NEVER = "NEVER"


# Actions that ALWAYS require explicit approval regardless of autonomy level
ALWAYS_APPROVE_ACTIONS = frozenset({
    "financial_transaction",
    "public_publish",
    "data_delete",
    "account_modify",
    "external_send",
})

SURFACE_NAMES = frozenset({
    "command", "flow", "markets", "intelligence", "network",
})

# Default base directory -- can be overridden via constructor
_DEFAULT_BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)


def _now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _gen_id() -> str:
    """Generate a short unique ID."""
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Agent Registration Record
# ---------------------------------------------------------------------------

class AgentRecord:
    """Tracks a registered agent's metadata and status."""

    def __init__(
        self,
        name: str,
        capabilities: List[str],
        autonomy_level: AutonomyLevel,
    ):
        self.name = name
        self.capabilities = capabilities
        self.autonomy_level = autonomy_level
        self.status = "idle"
        self.registered_at = _now_iso()
        self.last_active = self.registered_at

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "autonomy_level": self.autonomy_level.value,
            "status": self.status,
            "registered_at": self.registered_at,
            "last_active": self.last_active,
        }


# ---------------------------------------------------------------------------
# Approval Item
# ---------------------------------------------------------------------------

class ApprovalItem:
    """An item waiting for human approval."""

    def __init__(
        self,
        item_id: str,
        agent_name: str,
        action: str,
        details: dict,
    ):
        self.item_id = item_id
        self.agent_name = agent_name
        self.action = action
        self.details = details
        self.status = "pending"  # pending | approved | rejected
        self.created_at = _now_iso()
        self.resolved_at: Optional[str] = None
        self.resolved_by: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "agent_name": self.agent_name,
            "action": self.action,
            "details": self.details,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
        }


# ---------------------------------------------------------------------------
# AgentBus
# ---------------------------------------------------------------------------

class AgentBus:
    """
    Central nervous system for Permanence OS agents.

    Provides unified access to the Entity Graph, all surfaces, the Inbox
    overlay, persistent memory, and a pub/sub event system.

    Thread-safe. All operations are wrapped in try/except for graceful
    degradation.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self._base_dir = base_dir or _DEFAULT_BASE_DIR
        self._lock = threading.Lock()

        # -- Subsystem references --
        self._graph = None
        self._agents: Dict[str, AgentRecord] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._pending_approvals: Dict[str, ApprovalItem] = {}

        # -- Storage paths --
        storage_dir = os.path.join(self._base_dir, "permanence_storage")
        self._state_path = os.path.join(storage_dir, "agent_state.json")
        self._audit_path = os.path.join(storage_dir, "agent_audit.jsonl")
        self._inbox_path = os.path.join(
            self._base_dir, "memory", "inbox", "inbox.json"
        )
        self._memory_dir = os.path.join(self._base_dir, "memory")

        # Ensure storage directories exist
        try:
            os.makedirs(storage_dir, exist_ok=True)
            os.makedirs(os.path.join(self._memory_dir, "inbox"), exist_ok=True)
        except OSError:
            pass  # Best-effort; will fail gracefully on actual use

    # -- Entity Graph Access ------------------------------------------------

    @property
    def graph(self):
        """
        Lazy-loaded Entity Graph instance.

        Returns the shared EntityGraph connected to the production database.
        Agents use this to create, read, update, and link entities.
        """
        if self._graph is None:
            try:
                from core.entity_graph import EntityGraph
                db_path = os.path.join(
                    self._base_dir, "permanence_storage", "entity_graph.db"
                )
                self._graph = EntityGraph(db_path=db_path)
            except Exception as e:
                raise RuntimeError(
                    f"AgentBus: failed to initialize Entity Graph: {e}"
                )
        return self._graph

    # -- Agent Registration -------------------------------------------------

    def register(
        self,
        agent_name: str,
        capabilities: List[str],
        autonomy_level: str,
    ) -> dict:
        """
        Register an agent with the bus.

        Args:
            agent_name: Unique name for the agent (e.g. "sentinel")
            capabilities: List of capability tags (e.g. ["governance"])
            autonomy_level: One of FULL_AUTO, SOFT_APPROVAL,
                            EXPLICIT_APPROVAL, NEVER

        Returns:
            Agent record as dict.

        Raises:
            ValueError: If autonomy_level is invalid.
        """
        try:
            level = AutonomyLevel(autonomy_level)
        except ValueError:
            raise ValueError(
                f"Invalid autonomy level '{autonomy_level}'. "
                f"Must be one of: {[a.value for a in AutonomyLevel]}"
            )

        with self._lock:
            record = AgentRecord(agent_name, capabilities, level)
            self._agents[agent_name] = record
            self._save_state()

        self.log(agent_name, "registered", {
            "capabilities": capabilities,
            "autonomy_level": autonomy_level,
        })

        return record.to_dict()

    def get_agent(self, agent_name: str) -> Optional[dict]:
        """Get a registered agent's record."""
        with self._lock:
            record = self._agents.get(agent_name)
            return record.to_dict() if record else None

    def list_agents(self) -> List[dict]:
        """List all registered agents."""
        with self._lock:
            return [r.to_dict() for r in self._agents.values()]

    # -- Search -------------------------------------------------------------

    def search(self, query: str, entity_type: Optional[str] = None,
               limit: int = 20) -> list:
        """
        Search across the Entity Graph.

        Delegates to EntityGraph.search() which does LIKE matching on
        titles and properties.
        """
        try:
            return self.graph.search(query, entity_type=entity_type,
                                     limit=limit)
        except Exception as e:
            self.log("bus", "search_failed", {"query": query, "error": str(e)})
            return []

    # -- Inbox Overlay ------------------------------------------------------

    def inbox_push(self, item: dict) -> dict:
        """
        Push an item to the Inbox overlay.

        The item dict should contain at minimum:
            - title (str): what happened
            - source (str): which agent or surface sent it

        Additional fields (type, priority, surface, entity_id) are optional.

        Returns the enriched item with generated id and timestamp.
        """
        enriched = {
            "id": _gen_id(),
            "timestamp": _now_iso(),
            "read": False,
            **item,
        }

        try:
            # Also create as Entity Graph node for queryability
            self.graph.create_entity(
                entity_type="INBOX_ITEM",
                title=item.get("title", "Inbox item"),
                properties=enriched,
                created_by=item.get("source", "bus"),
            )
        except Exception:
            pass  # Graph write is best-effort

        # Append to inbox JSON file
        try:
            inbox = self._load_inbox()
            inbox.append(enriched)
            self._save_inbox(inbox)
        except Exception:
            pass  # File write is best-effort

        # Fire event
        self._emit("inbox_push", enriched)

        return enriched

    def inbox_list(self, unread_only: bool = False) -> list:
        """List inbox items, optionally filtered to unread only."""
        try:
            inbox = self._load_inbox()
            if unread_only:
                return [i for i in inbox if not i.get("read")]
            return inbox
        except Exception:
            return []

    # -- Surface Data Access ------------------------------------------------

    def surface_data(self, surface_name: str) -> dict:
        """
        Get data for a specific surface.

        Surfaces:
            command    -- approvals, missions, agent status
            flow       -- tasks, content pipeline, reminders
            markets    -- portfolio, positions, trades, watchlist
            intelligence -- notes, documents, research, memory
            network    -- contacts, messages, relationships

        Returns a dict with the surface's data from the Entity Graph.
        """
        surface_name = surface_name.lower()
        if surface_name not in SURFACE_NAMES:
            raise ValueError(
                f"Unknown surface '{surface_name}'. "
                f"Must be one of: {sorted(SURFACE_NAMES)}"
            )

        type_map = {
            "command": ["APPROVAL", "MISSION", "AGENT", "DECISION"],
            "flow": ["TASK", "REMINDER"],
            "markets": ["TICKER", "STRATEGY", "POSITION", "PORTFOLIO"],
            "intelligence": ["NOTE", "DOCUMENT", "MEMORY"],
            "network": ["CONTACT", "COMPANY"],
        }

        results = {}
        try:
            for entity_type in type_map.get(surface_name, []):
                entities = self.graph.query({
                    "entity_type": entity_type,
                    "status": "active",
                })
                results[entity_type.lower()] = entities
        except Exception as e:
            results["error"] = str(e)

        return {
            "surface": surface_name,
            "data": results,
            "retrieved_at": _now_iso(),
        }

    # -- Memory Access ------------------------------------------------------

    def memory_read(self, key: str) -> Any:
        """
        Read a value from persistent agent memory.

        Memory is stored as JSON files in the memory/ directory,
        keyed by a simple string key (dot-separated path supported).
        """
        try:
            mem_file = os.path.join(self._memory_dir, "agent_memory.json")
            if not os.path.exists(mem_file):
                return None
            with open(mem_file, "r") as f:
                data = json.load(f)
            return data.get(key)
        except (OSError, json.JSONDecodeError):
            return None

    def memory_write(self, key: str, value: Any) -> bool:
        """
        Write a value to persistent agent memory.

        Returns True on success, False on failure.
        """
        try:
            mem_file = os.path.join(self._memory_dir, "agent_memory.json")
            data = {}
            if os.path.exists(mem_file):
                with open(mem_file, "r") as f:
                    data = json.load(f)
            data[key] = value
            with open(mem_file, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except (OSError, json.JSONDecodeError):
            return False

    # -- Audit Logging ------------------------------------------------------

    def log(self, agent_name: str, action: str, details: Any = None) -> dict:
        """
        Log an agent action to the append-only audit trail.

        Every action is:
          1. Written to agent_audit.jsonl
          2. Stored as an AGENT_ACTION entity in the graph
          3. Linked to the agent entity if one exists

        Returns the log entry dict.
        """
        entry = {
            "id": _gen_id(),
            "timestamp": _now_iso(),
            "agent": agent_name,
            "action": action,
            "details": details,
        }

        # 1. Append to JSONL audit file
        try:
            with open(self._audit_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass  # Logging must never break the caller

        # 2. Store as Entity Graph node (best-effort)
        try:
            self.graph.create_entity(
                entity_type="AGENT_ACTION",
                title=f"{agent_name}:{action}",
                properties=entry,
                created_by=agent_name,
            )
        except Exception:
            pass

        return entry

    def audit_trail(self, agent_name: Optional[str] = None,
                    limit: int = 50) -> list:
        """
        Read the audit trail, optionally filtered by agent.

        Returns most recent entries first.
        """
        entries = []
        try:
            if not os.path.exists(self._audit_path):
                return []
            with open(self._audit_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if agent_name and entry.get("agent") != agent_name:
                            continue
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []

        # Most recent first, capped at limit
        return list(reversed(entries[-limit:]))

    # -- Approval Workflow --------------------------------------------------

    def request_approval(
        self,
        agent_name: str,
        action: str,
        details: dict,
    ) -> ApprovalItem:
        """
        Submit an action for human approval.

        Creates an approval item, pushes it to the inbox, and returns
        the item. The agent must wait for approve() or reject() to be
        called on this item before proceeding.
        """
        item_id = _gen_id()
        approval = ApprovalItem(item_id, agent_name, action, details)

        with self._lock:
            self._pending_approvals[item_id] = approval

        # Push to inbox so the human sees it
        self.inbox_push({
            "title": f"Approval needed: {action}",
            "source": agent_name,
            "type": "approval_request",
            "priority": "high",
            "approval_id": item_id,
            "details": details,
        })

        self.log(agent_name, "approval_requested", {
            "item_id": item_id,
            "action": action,
        })

        self._emit("approval_needed", approval.to_dict())

        return approval

    def approve(self, item_id: str, approved_by: str = "user") -> Optional[dict]:
        """
        Approve a pending approval item.

        Returns the updated approval dict, or None if not found.
        """
        with self._lock:
            approval = self._pending_approvals.get(item_id)
            if not approval:
                return None
            approval.status = "approved"
            approval.resolved_at = _now_iso()
            approval.resolved_by = approved_by

        self.log("bus", "approval_granted", {
            "item_id": item_id,
            "approved_by": approved_by,
            "agent": approval.agent_name,
            "action": approval.action,
        })

        self._emit("approval_resolved", approval.to_dict())
        return approval.to_dict()

    def reject(self, item_id: str, rejected_by: str = "user") -> Optional[dict]:
        """
        Reject a pending approval item.

        Returns the updated approval dict, or None if not found.
        """
        with self._lock:
            approval = self._pending_approvals.get(item_id)
            if not approval:
                return None
            approval.status = "rejected"
            approval.resolved_at = _now_iso()
            approval.resolved_by = rejected_by

        self.log("bus", "approval_rejected", {
            "item_id": item_id,
            "rejected_by": rejected_by,
            "agent": approval.agent_name,
            "action": approval.action,
        })

        self._emit("approval_resolved", approval.to_dict())
        return approval.to_dict()

    def check_approval(self, item_id: str) -> Optional[dict]:
        """Check the status of an approval item."""
        with self._lock:
            approval = self._pending_approvals.get(item_id)
            return approval.to_dict() if approval else None

    def can_act(self, agent_name: str, action: str) -> dict:
        """
        Check whether an agent can perform an action given its autonomy level.

        Returns:
            {
                "allowed": bool,
                "requires_approval": bool,
                "reason": str,
            }

        Rules:
          - ALWAYS_APPROVE_ACTIONS always require explicit approval
          - NEVER autonomy: action is blocked entirely
          - EXPLICIT_APPROVAL: must request and receive approval first
          - SOFT_APPROVAL: can act but gets flagged for review
          - FULL_AUTO: can act freely (except ALWAYS_APPROVE_ACTIONS)
        """
        with self._lock:
            record = self._agents.get(agent_name)

        if not record:
            return {
                "allowed": False,
                "requires_approval": False,
                "reason": f"Agent '{agent_name}' not registered",
            }

        # Always-approve actions override autonomy level
        if action in ALWAYS_APPROVE_ACTIONS:
            return {
                "allowed": False,
                "requires_approval": True,
                "reason": f"Action '{action}' always requires explicit approval",
            }

        level = record.autonomy_level

        if level == AutonomyLevel.NEVER:
            return {
                "allowed": False,
                "requires_approval": False,
                "reason": f"Agent '{agent_name}' has NEVER autonomy",
            }

        if level == AutonomyLevel.EXPLICIT_APPROVAL:
            return {
                "allowed": False,
                "requires_approval": True,
                "reason": "Agent requires explicit approval for all actions",
            }

        if level == AutonomyLevel.SOFT_APPROVAL:
            return {
                "allowed": True,
                "requires_approval": True,
                "reason": "Agent can act but action is flagged for review",
            }

        # FULL_AUTO
        return {
            "allowed": True,
            "requires_approval": False,
            "reason": "Agent has full autonomy for this action",
        }

    # -- Agent Status -------------------------------------------------------

    def status(self, agent_name: str, new_status: Optional[str] = None) -> Optional[str]:
        """
        Get or set an agent's status.

        Valid statuses: idle, active, error, blocked

        If new_status is provided, sets the status and returns it.
        Otherwise returns the current status.
        Returns None if agent not found.
        """
        valid_statuses = {"idle", "active", "error", "blocked"}

        with self._lock:
            record = self._agents.get(agent_name)
            if not record:
                return None

            if new_status is not None:
                if new_status not in valid_statuses:
                    raise ValueError(
                        f"Invalid status '{new_status}'. "
                        f"Must be one of: {sorted(valid_statuses)}"
                    )
                record.status = new_status
                record.last_active = _now_iso()
                self._save_state()

            return record.status

    # -- Event System -------------------------------------------------------

    def on(self, event_name: str, callback: Callable) -> None:
        """
        Subscribe to an event.

        Supported events:
            new_task, approval_needed, approval_resolved,
            market_alert, new_message, inbox_push, agent_registered
        """
        with self._lock:
            if event_name not in self._event_handlers:
                self._event_handlers[event_name] = []
            self._event_handlers[event_name].append(callback)

    def off(self, event_name: str, callback: Callable) -> bool:
        """
        Unsubscribe from an event.

        Returns True if the callback was found and removed.
        """
        with self._lock:
            handlers = self._event_handlers.get(event_name, [])
            if callback in handlers:
                handlers.remove(callback)
                return True
            return False

    def emit(self, event_name: str, data: Any = None) -> int:
        """
        Emit an event (public interface for agents to fire custom events).

        Returns the number of handlers that were called.
        """
        return self._emit(event_name, data)

    # -- Private Helpers ----------------------------------------------------

    def _emit(self, event_name: str, data: Any = None) -> int:
        """Fire all handlers for an event. Errors in handlers are swallowed."""
        with self._lock:
            handlers = list(self._event_handlers.get(event_name, []))

        called = 0
        for handler in handlers:
            try:
                handler(data)
                called += 1
            except Exception:
                pass  # Event handlers must never break the bus
        return called

    def _load_inbox(self) -> list:
        """Load inbox items from disk."""
        if not os.path.exists(self._inbox_path):
            return []
        with open(self._inbox_path, "r") as f:
            return json.load(f)

    def _save_inbox(self, items: list) -> None:
        """Save inbox items to disk."""
        os.makedirs(os.path.dirname(self._inbox_path), exist_ok=True)
        with open(self._inbox_path, "w") as f:
            json.dump(items, f, indent=2)

    def _save_state(self) -> None:
        """Persist agent registration state to disk (best-effort)."""
        try:
            state = {
                name: record.to_dict()
                for name, record in self._agents.items()
            }
            os.makedirs(os.path.dirname(self._state_path), exist_ok=True)
            with open(self._state_path, "w") as f:
                json.dump(state, f, indent=2)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_bus_instance: Optional[AgentBus] = None
_bus_lock = threading.Lock()


def get_bus(base_dir: Optional[str] = None) -> AgentBus:
    """
    Get the singleton AgentBus instance.

    Pass base_dir on the first call to configure the storage root.
    Subsequent calls return the same instance regardless of base_dir.
    """
    global _bus_instance
    with _bus_lock:
        if _bus_instance is None:
            _bus_instance = AgentBus(base_dir=base_dir)
        return _bus_instance


def reset_bus() -> None:
    """
    Reset the singleton bus instance.

    Only use in tests or when reinitializing the system.
    """
    global _bus_instance
    with _bus_lock:
        _bus_instance = None
