# Finance Governance Profile

This system should be operated with controlled autonomy, not free autonomy.

## Operating Principle

The agent may:
- choose providers and models dynamically by task
- route finance research, valuation, and risk work to stronger models
- use lower-cost models for routine classification and formatting

The agent may not:
- execute financial actions without explicit human approval
- silently change long-lived secrets or provider credentials
- degrade high-stakes finance tasks to weak/local models without an explicit budget policy

## Finance Task Types

Use these task types when you want governed finance-specialized routing:

- `finance_analysis`
- `financial_review`
- `market_monitoring`
- `portfolio_risk`
- `valuation`

## Expected Routing Behavior

- `finance_analysis`, `portfolio_risk`, `valuation`
  - treated as high-complexity finance tasks
  - routed to strongest available paid models by provider
- `financial_review`, `market_monitoring`
  - treated as finance tasks that still require paid-model quality in hybrid mode
- routine tasks like `classification`, `summarization`, `formatting`
  - can still go to lower-cost/local models

## Governance Flags

Pass these context flags for stronger safeguards:

- `financial_action: true`
  - marks the task as high-risk
- `requires_approval: true`
  - preserves a human approval checkpoint
- `portfolio_data: true`
  - marks the task as finance-domain
- `market_data: true`
  - marks the task as finance-domain
- `external_write: true`
  - marks actions that affect outside systems

## Recommended Live Operating Mode

- keep dynamic provider routing enabled
- keep approval gates for:
  - financial actions
  - external writes
  - credential/config changes
- prefer:
  - Anthropic / OpenAI / xAI / OpenClaw for finance reasoning
  - Ollama only for routine low-risk local tasks

## Practical Rule

If the task can move money, alter a position, change a credential, or modify infrastructure:

- require approval
- log the route decision
- do not let the system act unattended
