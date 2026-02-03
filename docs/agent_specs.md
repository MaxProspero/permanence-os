# Agent Specifications

## Polemarch (Governor)
- Validates tasks against Canon
- Assigns risk tiers
- Enforces budgets
- Routes execution
- Escalates to human authority
- Logs every decision

## Planner
- Converts goals to structured specs
- Defines success criteria and constraints
- Estimates resource needs

## Researcher
- Gathers verified sources with provenance
- No speculation beyond sources
- Can ingest tool outputs into sources.json
- Can ingest local documents into sources.json

## Executor
- Produces outputs strictly from approved plans
- Can package a human-provided draft into outputs
- Can auto-compose a minimal report from source notes
- No scope changes

## Reviewer
- Evaluates outputs against spec/rubric
- Provides pass/fail and required changes
- Rejects placeholder or missing provenance sections

## Conciliator
- Accept/retry/escalate decision after review
- Escalates after retry limit


## HR Agent (The Shepherd)
- Monitors system health and agent relations
- Generates weekly System Health reports
- Surfaces patterns and recommendations
- Read-only; cannot override or block execution

## Compliance Gate
- Reviews outbound actions for legal/ethical/identity compliance
- Verdicts: APPROVE | HOLD | REJECT
- Sits after Reviewer for external actions

## Department Agents (Stubs)
- Email Agent
- Device Agent
- Social Media Agent
- Health Agent
- Briefing Agent
- Trainer Agent
- Therapist Agent
