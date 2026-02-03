# Contributing to Permanence OS

Thanks for helping improve Permanence OS. This project is governance‑first and expects disciplined changes.

## Principles
- **Canon is law**: no silent changes to `canon/base_canon.yaml`.
- **Log everything**: avoid untracked behavior and hidden state.
- **Separation of duties**: do not collapse roles (Planner, Researcher, Executor, Reviewer, Compliance).

## Setup
```bash
git clone <repo>
cd permanence-os
pip install -r requirements.txt
```

## Change Process
1) **Describe intent** in your PR summary.
2) **Update tests** if behavior changes.
3) **Update docs** if new commands or files are added.
4) **Update CHANGELOG.md** for any user‑visible change.

## Canon Changes (Required Ceremony)
Use `docs/canon_change_template.md` and include:
- Rationale
- Impact analysis
- Rollback plan
- Version bump
- Human approval

## Tests
```bash
python cli.py test
```

## Style
- Prefer clarity over cleverness.
- Keep files small and focused.
- Avoid non‑ASCII unless the file already uses it.

## Security
Do not commit:
`.env`, tokens, keys, or personal data.

If unsure, ask before changing governance logic.
