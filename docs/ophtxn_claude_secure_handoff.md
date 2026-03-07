# Ophtxn Claude Code Secure Handoff

Use this flow to share keys, CLI context, and operating notes with Claude Code without exposing secrets in GitHub.

## What to Use

- Canonical local-only handoff file:
  - `/Users/paytonhicks/Code/permanence-os/private/ophtxn_claude_handoff.local.md`
- Public template (safe to commit):
  - `docs/ophtxn_claude_handoff_template.md`

## Rules

1. Never store raw secrets in committed files (`README.md`, `docs/*`, scripts).
2. Keep secret values only in:
   - `.env` (already gitignored), or
   - `private/*.local.*` files (gitignored), or
   - macOS Keychain / provider vaults.
3. Run a secret scan before push:

```bash
python cli.py secret-scan --staged
```

4. Lock local handoff file permissions:

```bash
chmod 600 private/ophtxn_claude_handoff.local.md
```

## Recommended Handoff Structure

Use these sections inside your local handoff file:

- `Mission Context`: current goals and constraints.
- `System State`: what is running, what is broken, what changed last.
- `Credential Map`: secret alias + storage location (not raw values unless required).
- `CLI Runbook`: commands you run daily/weekly.
- `Integrations`: Telegram/Discord/X/OpenClaw status and notes.
- `Approval Boundaries`: what can run automatically vs needs approval.
- `Open Tasks`: next priorities.

## How To Use With Claude Code

In Claude Code, message:

```text
Read /Users/paytonhicks/Code/permanence-os/private/ophtxn_claude_handoff.local.md
and use it as my secure operating context for this session.
```

Then ask for work normally.

## Rotation and Hygiene

- Rotate exposed/reused keys immediately.
- If a token ever appears in chat or commit history, replace it and remove it from tracked files.
- Keep one source of truth per secret to reduce stale credentials.
