# Testing Standards

- All changes must maintain 0 new test failures
- Current baseline: 960+ tests across 163+ test files
- Use pytest with tmp_path fixtures for file I/O tests
- Use monkeypatch for module-level constants
- Use unittest.mock.patch for network calls
- Never skip tests without documented justification
- Every new script gets a corresponding test file in tests/
- Test file naming: test_{module_name}.py
- Test class naming: TestFeatureName
- Run full suite: pytest -q --ignore=tests/test_arena_state.py
