# OCA Client Context

## Relevant Files
- scripts/oca_lead_generator.py -- Lead scraping and scoring
- scripts/oca_proposal_generator.py -- Proposal generation
- scripts/sales_pipeline.py -- Sales pipeline tracking
- memory/working/oca_lead_config.json -- Lead gen configuration
- dashboard_api.py -- /api/oca/* endpoints
- tests/test_oca_lead_generator.py -- Lead gen tests
- tests/test_oca_proposal_generator.py -- Proposal tests

## Key Concepts
- Boring Wedge GTM: solve mundane pain first, earn trust, expand
- SWIFT: Set up -> Workflow -> Iterate -> Formalize -> Trigger
- 5 workflow templates: lead_gen, appointment_booking, review_management, invoice_follow_up, price_monitoring
- Lead scoring: 0-100 based on industry fit, size, accessibility
- All proposals pass voice compliance before delivery

## Testing
python3 -m pytest tests/test_oca_lead_generator.py tests/test_oca_proposal_generator.py -v
