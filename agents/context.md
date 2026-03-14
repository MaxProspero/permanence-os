# Agents Workspace Context

## Goal
Multi-agent system providing autonomous intelligence capabilities with governance controls.

## Agent Roster

### Core Agents (top-level)
| Agent | File | Purpose |
|-------|------|---------|
| Base | base.py | Base agent class -- all agents inherit from this |
| Compliance Gate | compliance_gate.py | Governance enforcement, approval checks |
| Conciliator | conciliator.py | Conflict resolution between agents |
| Executor | executor.py | Action execution with approval gates |
| Identity | identity.py | Identity and authentication management |
| King Bot | king_bot.py | Top-level orchestrator, decision authority |
| Planner | planner.py | Task planning and decomposition |
| Researcher | researcher.py | Research and information gathering |
| Researcher Adapters | researcher_adapters.py | Data source adapters for researcher |
| Reviewer | reviewer.py | Output review and quality control |
| Synthesis Agent | synthesis_agent.py | Information synthesis and summarization |
| Utils | utils.py | Shared agent utilities |

### Department Agents (/agents/departments/)
| Agent | File | Department | Purpose |
|-------|------|-----------|---------|
| Briefing Agent | briefing_agent.py | Briefing | Daily briefing generation |
| Device Agent | device_agent.py | Hardware | Device management and control |
| Email Agent | email_agent.py | Comms | Email processing and triage |
| Health Agent | health_agent.py | Health | Health data monitoring |
| HR Agent | hr_agent.py | HR | Agent workforce management |
| Reception Agent | reception_agent.py | Reception | Incoming request routing |
| Social Agent | social_agent.py | Comms | Social media management |
| Therapist Agent | therapist_agent.py | Health | Mental health and reflection |
| Trainer Agent | trainer_agent.py | Training | Agent training and evaluation |

## Routing Table
| Task | Read These Files | Skip These Files |
|------|-----------------|-----------------|
| Fix Agent Bug | Target agent .py, base.py, its test | /site, /design, /scripts |
| Add New Agent | base.py, departments/__init__.py, similar agent | /site, /design |
| Add Department | departments/__init__.py, base.py | /site, /scripts |
| Governance Change | compliance_gate.py, executor.py | /site, /design |
| Agent Comms Issue | Target dept agent, comms_*.py in /scripts | /site, /design |

## Key Test Files
| Test | Covers |
|------|--------|
| test_agents.py | Core agent functionality |
| test_compliance_gate.py | Governance gate logic |
| test_executor_compiled.py | Executor behavior |
| test_email_agent.py | Email agent |
| test_health_agent.py | Health agent |
| test_hr_agent.py | HR agent |
| test_interface_agent.py | Interface agent (in /core) |

## Architecture Notes
- All agents extend the Base class in base.py
- The King Bot is the top-level decision authority
- The Compliance Gate must approve high-stakes actions before the Executor runs them
- The Conciliator resolves conflicts when agents disagree
- Department agents are organized by functional area under /agents/departments/
- Agent state is managed through /core/memory.py and /core/storage.py
