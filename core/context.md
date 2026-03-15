# Core Workspace Context

## Goal
Core modules providing memory, model routing, spending controls, and system infrastructure for Permanence OS.

## Modules

| Module | File | Purpose |
|--------|------|---------|
| Init | __init__.py | Core package initialization |
| Cost Tracker | cost_tracker.py | API cost tracking and budget monitoring |
| Device Control | device_control.py | Hardware device control interface |
| Interface Agent | interface_agent.py | Interface between user and agent system |
| Memory | memory.py | Persistent cross-session memory system |
| Model Judge | model_judge.py | Model output quality evaluation |
| Model Router | model_router.py | Route requests to appropriate AI models |
| Polemarch | polemarch.py | Strategic command and coordination layer |
| Spending Gate | spending_gate.py | Spending approval and budget enforcement |
| Storage | storage.py | File and data storage abstraction |
| Synthesis DB | synthesis_db.py | Synthesis database for knowledge storage |
| Synthesis DB Compat | synthesis_db_compat.py | Backward compatibility layer for synthesis DB |
| Task Planner | task_planner.py | Task decomposition and scheduling |

## Routing Table
| Task | Read These Files | Skip These Files |
|------|-----------------|-----------------|
| Memory Bug | memory.py, storage.py, test_episodic_memory.py | /site, /design, /scripts |
| Model Routing | model_router.py, test_model_router*.py | /site, /design |
| Spending Issue | spending_gate.py, cost_tracker.py, related tests | /site, /design |
| Add Model Provider | model_router.py, test_model_router_providers.py | /site, /agents |
| Storage Change | storage.py, synthesis_db.py, memory.py | /site, /design |
| Cost Tracking | cost_tracker.py, spending_gate.py | /site, /design |

## Key Test Files
| Test | Covers |
|------|--------|
| test_cost_tracker.py | Cost tracking logic |
| test_device_control.py | Device control |
| test_interface_agent.py | Interface agent behavior |
| test_episodic_memory.py | Memory system |
| test_model_judge.py | Model output judging |
| test_model_router.py | Basic model routing |
| test_model_router_budget.py | Budget-aware routing |
| test_model_router_modes.py | Routing mode selection |
| test_model_router_providers.py | Provider integration |
| test_model_registry_providers.py | Model registry |

## Architecture Notes
- Memory (memory.py) is the persistent state layer -- all agents read/write through it
- Model Router (model_router.py) selects the best model for each request based on task type, budget, and availability
- Spending Gate (spending_gate.py) enforces budget caps -- no API call proceeds without clearance
- Cost Tracker (cost_tracker.py) logs every API call cost for audit
- Storage (storage.py) abstracts file system and database access
- Synthesis DB (synthesis_db.py) stores synthesized knowledge for retrieval
- Task Planner (task_planner.py) breaks complex tasks into executable steps
- Polemarch (polemarch.py) provides strategic coordination across subsystems

## Dependencies
- Core modules are imported by /agents and /scripts
- Core should NOT import from /agents, /scripts, or /site
- Core depends on standard library + requirements.txt packages only
