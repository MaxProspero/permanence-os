#!/usr/bin/env python3
"""Pre-write hook: scan file content for potential secrets before writing.

Returns non-zero exit code if secrets detected.
Used by Claude Code hooks to prevent accidental secret commits.
"""

import re
import sys

SECRET_PATTERNS = [
    (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"][a-zA-Z0-9_\-]{20,}['\"]", "API key assignment"),
    (r"(?i)(secret|token)\s*[=:]\s*['\"][a-zA-Z0-9_\-]{20,}['\"]", "Secret/token assignment"),
    (r"(?i)password\s*[=:]\s*['\"][^'\"]{8,}['\"]", "Password literal"),
    (r"sk-[a-zA-Z0-9]{20,}", "OpenAI-style API key"),
    (r"sk-ant-[a-zA-Z0-9\-]{20,}", "Anthropic API key"),
    (r"ghp_[a-zA-Z0-9]{36,}", "GitHub personal access token"),
    (r"xoxb-[a-zA-Z0-9\-]{20,}", "Slack bot token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key ID"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer token"),
]

# Patterns that are safe (env var references, not actual secrets)
SAFE_PATTERNS = [
    r"os\.environ",
    r"os\.getenv",
    r"PERMANENCE_",
    r"process\.env",
    r"\{.*_KEY\}",
    r"your[_-]?api[_-]?key",
    r"fake[_-]?key",
    r"test[_-]?key",
    r"example",
]


def scan_content(content: str) -> list[dict]:
    """Scan content for potential secrets."""
    violations = []
    for pattern, description in SECRET_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            # Check if match is in a safe context
            for match in matches:
                match_str = match if isinstance(match, str) else match[0]
                line_context = ""
                for line in content.split("\n"):
                    if match_str in line:
                        line_context = line.strip()
                        break
                is_safe = any(re.search(sp, line_context) for sp in SAFE_PATTERNS)
                if not is_safe:
                    violations.append({
                        "type": description,
                        "match": match_str[:30] + "..." if len(match_str) > 30 else match_str,
                        "context": line_context[:80],
                    })
    return violations


def main():
    if len(sys.argv) < 2:
        sys.exit(0)

    file_path = sys.argv[1]
    try:
        with open(file_path, "r") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        sys.exit(0)  # Can't read file, not a text file

    violations = scan_content(content)
    if violations:
        print(f"SECRET SCAN FAILED: {len(violations)} potential secret(s) detected in {file_path}")
        for v in violations:
            print(f"  [{v['type']}] {v['match']}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
