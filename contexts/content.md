# Content Context

## Relevant Files
- scripts/content_generator.py -- Content generation pipeline
- scripts/social_draft_queue.py -- Draft queue management
- scripts/social_research_ingest.py -- Research ingestion
- scripts/bookmark_ingest.py -- Bookmark processing
- canon/brand_identity.yaml -- Voice rules source
- tests/test_content_generator.py -- Content tests

## Key Concepts
- Voice compliance: FORBIDDEN_PATTERNS checked on all output
- Pipeline: bookmarks -> themes -> content -> voice check -> draft queue -> human review
- Formats: threads, newsletters, LinkedIn posts, short scripts
- Theme categories: ai_governance, agent_systems, trading_intelligence, etc.

## Testing
python3 -m pytest tests/test_content_generator.py -v
