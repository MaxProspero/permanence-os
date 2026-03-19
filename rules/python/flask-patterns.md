# Flask API Patterns

- All routes use log_api_call(endpoint_name) at entry
- Lazy imports for script modules (import inside route function)
- try/except per route with JSON error response
- Response format: {"key": value} or {"error": "message"}
- Use app.route decorator, not Blueprint (current architecture)
- Status codes: 200 success, 400 bad request, 500 server error
- AbortController timeout pattern on client-side fetches
- CORS headers handled at app level
- No blocking operations in request handlers
