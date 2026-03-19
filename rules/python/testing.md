# Python Testing Patterns

- Framework: pytest
- Fixtures: tmp_path for file I/O, monkeypatch for constants
- Mocking: unittest.mock.patch for network calls, external APIs
- Pattern: sys.path.insert(0, ...) at top of test file to import scripts
- Test data generators: _sample_data() helper functions
- Class grouping: TestFeatureName with test_specific_behavior methods
- Deterministic randomness: random.Random(seed) for reproducible tests
- Output verification: check both .md and .json outputs exist
- Voice compliance: verify generated content passes check_voice_compliance()
