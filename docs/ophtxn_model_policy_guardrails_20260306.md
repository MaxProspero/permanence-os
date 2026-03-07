# Ophtxn Model Policy and Guardrails (March 6, 2026)

Last updated: 2026-03-06 (US)

## Position

Ophtxn should not use jailbreak-style "uncensor" techniques to strip model safety behavior.

Instead, keep a clear governance layer that controls:

- which tools can run,
- what data can be accessed,
- what actions need approval,
- and what outputs are blocked/escalated.

## Why

- Safety bypass methods are brittle and degrade reliability.
- They increase legal/operational risk for a production product.
- Governance controls are durable and auditable.

## Recommended Architecture

1. **Base model policy:** keep provider safety baseline intact.
2. **Ophtxn policy engine:** apply project-specific allow/deny + escalation rules.
3. **Approval gate:** enforce human review for sensitive actions.
4. **Audit trail:** log decision rationale and tool usage for every high-impact task.

## Practical Controls

- Route financial/posting/account actions through approval queue only.
- Keep no-spend and low-cost mode defaults enabled.
- Isolate experimental prompts from production runtime.
- Store policy decisions in versioned docs + change logs.

## Product Framing

"Powerful but governed" is a stronger and more defensible product stance than "uncensored."

