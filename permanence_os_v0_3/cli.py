"""
Permanence OS — CLI v0.3
Unified entry point for all system operations.

Usage:
    python cli.py run <task>          Run a governed task
    python cli.py status              System health status
    python cli.py muse                Run Muse exploration cycle
    python cli.py audit               Run full architecture audit
    python cli.py twin <task>         Simulate a task via Digital Twin
    python cli.py chimera list        List available chimera traits
    python cli.py chimera compose     Compose a new chimera
    python cli.py proposals           View Muse proposal queue
    python cli.py zp-stats            Zero Point memory stats
    python cli.py test                Run test suite
"""

import sys
import os
import json
import uuid
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory.zero_point import ZeroPoint, MemoryType, ConfidenceLevel
from special.muse_agent import MuseAgent, MuseExplorationMode
from special.digital_twin import DigitalTwinSimulator
from special.chimera_builder import ChimeraBuilder
from special.arch_evolution_agent import ArchitectureEvolutionAgent
from core.polemarch import Polemarch


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  PERMANENCE OS v0.3 — {title}")
    print(f"{'='*60}\n")


def cmd_status():
    """System health status."""
    print_header("SYSTEM STATUS")

    # Zero Point stats
    zp = ZeroPoint()
    zp_stats = zp.get_stats()
    print(f"  Zero Point Memory:")
    print(f"    Total entries: {zp_stats['total_entries']}")
    print(f"    Reviewed: {zp_stats['reviewed']}")
    print(f"    Stale: {zp_stats['stale']}")
    print(f"    By type: {json.dumps(zp_stats['by_type'], indent=6)}")

    # Muse queue
    muse = MuseAgent()
    queue = muse.get_queue_status()
    print(f"\n  Muse Proposal Queue:")
    print(f"    Total: {queue['total']}")
    print(f"    Pending: {queue['pending']}")
    print(f"    Approved: {queue['approved']}")

    # Architecture health
    arch = ArchitectureEvolutionAgent()
    dash = arch.get_evolution_dashboard()
    print(f"\n  Architecture Evolution:")
    print(f"    Total audits: {dash['total_audits']}")
    print(f"    Total proposals: {dash['total_proposals']}")

    # Chimera status
    builder = ChimeraBuilder()
    active = builder.get_active_chimeras()
    print(f"\n  Active Chimeras: {len(active)}")
    for c in active:
        print(f"    - {c['name']} ({c['purpose'][:40]}...)")

    print(f"\n  System Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"  DNA Triad: Safety | Abundance | Service")
    print()


def cmd_muse():
    """Run Muse exploration cycle."""
    print_header("MUSE EXPLORATION CYCLE")

    muse = MuseAgent()
    results = muse.run_exploration_cycle(mode=MuseExplorationMode.DIVERGENT)

    for r in results:
        print(f"  Target: {r['target']}")
        print(f"  Status: {r['status']}")
        vectors = r['exploration_context']['available_improvements']
        print(f"  Improvement Vectors:")
        for v in vectors[:3]:
            print(f"    - {v}")
        print()

    print(f"  Exploration contexts generated: {len(results)}")
    print(f"  Feed these to LLM inference for creative proposal generation.")
    print()


def cmd_audit():
    """Run full architecture audit."""
    print_header("ARCHITECTURE AUDIT")

    arch = ArchitectureEvolutionAgent()
    result = arch.run_full_system_audit()

    print(f"  System Health: {result['system_health']}")
    print(f"  Status: {result['system_status']}")
    print(f"  Critical Components: {result['critical_components']}")
    print()

    for comp, data in result['components'].items():
        status_icon = "✓" if data['recommendation'] == "HEALTHY" else \
                      "⚠" if data['recommendation'] == "NEEDS_ATTENTION" else "✗"
        print(f"  {status_icon} {comp}")
        print(f"    Health: {data['health_score']} | {data['recommendation']}")
        print(f"    Weaknesses: {data['weaknesses']} | Opportunities: {data['opportunities']}")
        print()


def cmd_twin(task_desc: str):
    """Simulate a task via Digital Twin."""
    print_header("DIGITAL TWIN SIMULATION")

    twin = DigitalTwinSimulator()
    polemarch = Polemarch(canon_path="canon/")

    # Route through Polemarch first
    task = {
        "task_id": f"T-{uuid.uuid4().hex[:6]}",
        "goal": task_desc,
        "action": task_desc,
    }
    validation = polemarch.validate_task(task)
    print(f"  Polemarch Validation: {validation['status']}")
    print(f"  Risk Tier: {validation.get('risk_tier', 'N/A')}")
    print(f"  Twin Required: {validation.get('twin_required', False)}")
    print()

    # Run simulation
    report = twin.simulate(
        task_id=task["task_id"],
        action=task_desc,
        context={"goal": task_desc},
        risk_tier=validation.get("risk_tier", "MEDIUM"),
        agent_id="CLI-USER"
    )

    print(f"  Simulation Result: {report.result}")
    print(f"  Recommendation: {report.recommendation}")
    print(f"  Reversibility: {report.reversibility}")
    print(f"  Confidence: {report.confidence_in_simulation}")
    if report.escalation_reason:
        print(f"  Escalation Reason: {report.escalation_reason}")

    print(f"\n  Stress Tests:")
    for s in report.stress_scenarios:
        icon = "✓" if s['survives'] else "✗"
        print(f"    {icon} {s['scenario']}: {s['note']}")
    print()


def cmd_chimera_list():
    """List available chimera traits."""
    print_header("CHIMERA BUILDER — AVAILABLE TRAITS")

    builder = ChimeraBuilder()
    traits = builder.list_available_traits()

    current_figure = ""
    for t in traits:
        if t['figure'] != current_figure:
            current_figure = t['figure']
            print(f"\n  {t['figure']} ({t['domain']})")
        print(f"    → {t['trait']}: {t['description'][:70]}...")
    print()


def cmd_proposals():
    """View Muse proposal queue."""
    print_header("MUSE PROPOSAL QUEUE")

    muse = MuseAgent()
    status = muse.get_queue_status()

    print(f"  Total: {status['total']} | Pending: {status['pending']} | Approved: {status['approved']}")
    print()

    if status['top_scored']:
        print(f"  Top Scored Proposals:")
        for p in status['top_scored']:
            print(f"    [{p['score']}] {p['title']}")
            print(f"         Risk: {p['risk_tier']} | Impact: {p['estimated_impact']}")
    else:
        print(f"  No pending proposals. Run 'python cli.py muse' to generate ideas.")
    print()


def cmd_zp_stats():
    """Zero Point memory stats."""
    print_header("ZERO POINT MEMORY")

    zp = ZeroPoint()
    stats = zp.get_stats()

    print(f"  Total Entries: {stats['total_entries']}")
    print(f"  Reviewed: {stats['reviewed']}")
    print(f"  Unreviewed: {stats['unreviewed']}")
    print(f"  Stale: {stats['stale']}")
    print(f"  By Type: {json.dumps(stats['by_type'], indent=4)}")
    print()


def cmd_run(task_desc: str):
    """Run a governed task through the full pipeline."""
    print_header(f"TASK: {task_desc[:40]}")

    polemarch = Polemarch(canon_path="canon/")
    task = {
        "task_id": f"T-{uuid.uuid4().hex[:6]}",
        "goal": task_desc,
        "action": task_desc,
        "type": task_desc,
    }

    validation = polemarch.validate_task(task)
    print(f"  Status: {validation['status']}")
    print(f"  Risk: {validation.get('risk_tier', 'N/A')}")
    print(f"  Route: {validation.get('route_to', 'N/A')}")
    print(f"  Twin: {'REQUIRED' if validation.get('twin_required') else 'optional'}")

    if validation.get('twin_required'):
        print(f"\n  → Running Digital Twin simulation first...")
        cmd_twin(task_desc)

    print()


def main():
    if len(sys.argv) < 2:
        print_header("HELP")
        print("  Commands:")
        print("    status              System health")
        print("    muse                Run Muse exploration")
        print("    audit               Architecture audit")
        print("    twin <desc>         Simulate a task")
        print("    chimera list        Available traits")
        print("    proposals           View proposal queue")
        print("    zp-stats            Zero Point stats")
        print("    run <desc>          Run a governed task")
        print("    test                Run test suite")
        print()
        return

    cmd = sys.argv[1].lower()

    if cmd == "status":
        cmd_status()
    elif cmd == "muse":
        cmd_muse()
    elif cmd == "audit":
        cmd_audit()
    elif cmd == "twin" and len(sys.argv) > 2:
        cmd_twin(" ".join(sys.argv[2:]))
    elif cmd == "chimera" and len(sys.argv) > 2 and sys.argv[2] == "list":
        cmd_chimera_list()
    elif cmd == "proposals":
        cmd_proposals()
    elif cmd == "zp-stats":
        cmd_zp_stats()
    elif cmd == "run" and len(sys.argv) > 2:
        cmd_run(" ".join(sys.argv[2:]))
    elif cmd == "test":
        os.system("python -m pytest tests/ -v")
    else:
        print(f"Unknown command: {cmd}")
        print("Run 'python cli.py' for help.")


if __name__ == "__main__":
    main()
