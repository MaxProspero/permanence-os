# Python Coding Style

- Python 3.10+ with from __future__ import annotations
- Type hints on all function signatures
- Dataclasses for structured data (not NamedTuple unless immutable needed)
- pathlib.Path for all file operations
- try/except around ALL file I/O and network calls
- Specific exception types: OSError, json.JSONDecodeError, requests.RequestException
- Use json.dump/load with indent=2 for config files
- Lazy imports for heavy modules in API endpoints
- Constants at module level, UPPER_SNAKE_CASE
- BASE_DIR = Path(__file__).resolve().parents[N] pattern for paths
