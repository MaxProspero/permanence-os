# PowerShell helpers for Dell + WSL (Ubuntu) workflow.
# Usage (PowerShell):
#   cd C:\path\to\permanence-os
#   . .\automation\dell_wsl_helpers.ps1
#   perm-bootstrap <repo-url>
#   perm-cutover
#   perm-test
#   perm-run

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:PermanenceDistro = "Ubuntu"
$script:PermanenceRepoPath = "~/permanence-os"

function ubu {
    param(
        [Parameter(Mandatory = $true, Position = 0)]
        [string]$Command
    )
    wsl.exe -d $script:PermanenceDistro -- bash -lc $Command
    if ($LASTEXITCODE -ne 0) {
        throw "WSL command failed (exit $LASTEXITCODE): $Command"
    }
}

function Set-PermanenceWSLTarget {
    param(
        [string]$Distro = "Ubuntu",
        [string]$RepoPath = "~/permanence-os"
    )
    $script:PermanenceDistro = $Distro
    $script:PermanenceRepoPath = $RepoPath
    Write-Host "Target updated. Distro=$script:PermanenceDistro RepoPath=$script:PermanenceRepoPath"
}

function perm-bootstrap {
    param(
        [Parameter(Mandatory = $true, Position = 0)]
        [string]$RepoUrl
    )

    $repo = $script:PermanenceRepoPath

    ubu "sudo apt update && sudo apt install -y python3 python3-venv python3-pip git"
    ubu "if [ -d $repo/.git ]; then cd $repo && git pull --ff-only; else git clone $RepoUrl $repo; fi"
    ubu "cd $repo && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    ubu "cd $repo && [ -f .env ] || cp .env.example .env"
    ubu "cd $repo && grep -q '^PERMANENCE_STORAGE_ROOT=' .env || echo \"PERMANENCE_STORAGE_ROOT=/home/`$USER/permanence_storage\" >> .env"
    Write-Host "Bootstrap complete."
}

function perm-test {
    $repo = $script:PermanenceRepoPath
    ubu "cd $repo && source .venv/bin/activate && python cli.py test"
}

function perm-cutover {
    $repo = $script:PermanenceRepoPath
    ubu "cd $repo && bash automation/setup_dell_automation.sh && source .venv/bin/activate && python cli.py dell-cutover-verify"
}

function perm-run {
    $repo = $script:PermanenceRepoPath
    ubu "cd $repo && bash automation/run_briefing.sh && latest=\$(ls -t logs/automation/run_*.log | head -n 1) && echo \$latest && tail -n 80 \$latest"
}

Write-Host "Loaded helpers: ubu, perm-bootstrap, perm-test, perm-cutover, perm-run, Set-PermanenceWSLTarget"
