# Governance Context

## Relevant Files
- agents/compliance_gate.py -- Compliance validation
- agents/sentinel.py -- Constitutional referee
- core/spending_gate.py -- Spending authorization
- canon/dna.yaml -- Core identity DNA
- canon/brand_identity.yaml -- Brand rules
- canon/base_canon.yaml -- Base canon

## Key Concepts
- Prime Directive: Automation can assist, but human authority is final
- 60/30/10 Rule: 60% deterministic, 30% rule-based, 10% AI/LLM
- Spending gate: per-provider credit tracking with approval flow
- Compliance gate: DNA triad validation before execution
- Sentinel: constitutional veto power on governance violations

## Testing
python3 -m pytest tests/test_spending_gate.py tests/test_compliance_gate.py -v
