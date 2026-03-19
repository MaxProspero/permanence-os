# Coding Style -- Common Rules

- try/except on ALL file reads and network calls
- No bare exceptions -- catch specific error types (OSError, json.JSONDecodeError, requests.RequestException, etc.)
- AbortController on all frontend fetch calls
- No emojis anywhere in the codebase
- Use pathlib.Path for file paths in Python
- Use type hints on all function signatures
- Prefer dataclasses for structured data over plain dicts
- Keep functions under 50 lines; extract helpers for complex logic
- Use f-strings for string formatting (not .format() or %)
