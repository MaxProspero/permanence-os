# Dell Cutover Runbook

This runbook moves scheduled automation from Mac to Dell (Linux) with the same `7,12,19` cadence.

## 1. Prepare Dell

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

Clone the repo on Dell:

```bash
git clone <your-repo-url> ~/permanence-os
cd ~/permanence-os
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure `.env` on Dell

Create `~/permanence-os/.env` with at least:

```dotenv
PERMANENCE_STORAGE_ROOT=/path/to/storage
PERMANENCE_NOTEBOOKLM_SYNC=1
PERMANENCE_NOTEBOOKLM_SYNC_SLOT=19
PERMANENCE_PHASE_GATE_DOW=7
PERMANENCE_NOTEBOOKLM_FOLDER_ID=...
```

Notes:
- If LaCie is attached to Dell, use that mount path.
- If not, use a persistent local path and rsync backups later.

## 3. Install Linux Automation

```bash
cd ~/permanence-os
bash automation/setup_dell_automation.sh
```

This installs a managed cron block:
- `07:00`
- `12:00`
- `19:00`

## 4. Verify on Dell

Run once manually:

```bash
cd ~/permanence-os
bash automation/run_briefing.sh
latest=$(ls -t logs/automation/run_*.log | head -n 1)
tail -n 80 "$latest"
```

Expected:
- `Briefing Status: 0`
- `Digest Status: 0`
- daily gate/streak lines after evening runs

Verify cutover state:

```bash
python cli.py dell-cutover-verify
```

Expected:
- managed cron block found
- slots `07:00`, `12:00`, `19:00` present
- required env key `PERMANENCE_STORAGE_ROOT` present

## 5. Cutover (Single Scheduler Owner)

Use one host as scheduler owner to avoid duplicate runs.

- If Dell becomes owner:
  1. Keep Dell cron enabled.
  2. Disable Mac launchd:

```bash
launchctl unload ~/Library/LaunchAgents/com.permanence.briefing.plist
```

- If you revert to Mac later:
  1. Remove Dell cron block:

```bash
cd ~/permanence-os
bash automation/disable_dell_automation.sh
```
  2. Re-enable Mac launchd:

```bash
cd "/Users/paytonhicks/Documents/Permanence OS/permanence-os"
bash automation/setup_automation.sh
```

## 6. Weekly Gate

On weekly review day:

```bash
python cli.py phase-gate --days 7
```

Gate only passes when:
- strict reliability passes for the full window
- streak meets target (default `7`)
