# Dell Cutover (PowerShell + WSL)

Use this when your Dell workflow is PowerShell-first and pasting into a Linux shell is unreliable.

## 1. Open PowerShell on Dell

From your repo checkout in Windows (for example `C:\Users\perma\permanence-os`), load the helper:

```powershell
. .\automation\dell_wsl_helpers.ps1
```

This gives you:
- `ubu` (run one WSL bash command)
- `perm-bootstrap`
- `perm-test`
- `perm-cutover`
- `perm-run`

## 2. Bootstrap Repo + Python in WSL

```powershell
perm-bootstrap <your-repo-url>
```

This does the full base setup in Ubuntu WSL:
- apt packages (`python3`, `venv`, `pip`, `git`)
- clone/pull repo at `$HOME/permanence-os`
- create `.venv` + install `requirements.txt`
- create `.env` if missing
- add `PERMANENCE_STORAGE_ROOT` if missing

## 3. Verify and Cut Over

Run tests:

```powershell
perm-test
```

Install Linux cron schedule + verify:

```powershell
perm-cutover
```

Run one manual briefing and inspect latest log:

```powershell
perm-run
```

## 4. Keep Single Scheduler Owner

If Dell is now the owner, disable the Mac scheduler to avoid duplicate runs:

```bash
launchctl unload ~/Library/LaunchAgents/com.permanence.briefing.plist
```

## 5. Optional Target Overrides

If needed, change distro/repo path used by helpers:

```powershell
Set-PermanenceWSLTarget -Distro Ubuntu -RepoPath '$HOME/permanence-os'
```
