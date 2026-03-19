# Security Rules

- NEVER commit API keys, tokens, passwords, or credentials
- NEVER remove governance/approval gates
- NEVER bypass spending gate authorization
- NEVER disable circuit breakers or rate limiting
- NEVER expose internal API keys in client-facing code
- All API endpoints must use try/except with specific error handling
- All external data must be sanitized before use
- Environment variables for all secrets (PERMANENCE_* prefix)
- File paths must be validated before read/write operations
