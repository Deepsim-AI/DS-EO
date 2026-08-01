# deploy_agents.ps1 — Deploy DS-EO agent prompt files to target location (Windows)
# Usage: deploy_agents.ps1 --target <path>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PkgRoot = (Get-Item "$ScriptDir\..").FullName
$AgentsSrc = "$PkgRoot\agents"

$AgentFiles = @('cto.md','implementer.md','pm.md','reviewer.md')

if (-not $Args -or $Args[0] -ne "--target") {
    Write-Host "Usage: deploy_agents.ps1 --target <path>"
    exit 0
}

$TargetDir = if ($Args.Count -ge 2) { $Args[1] } else { throw "Usage: deploy_agents.ps1 --target <path>" }

if (-not $TargetDir) {
    Write-Host "Error: Target directory required. Use --target <path>"
    exit 1
}

New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

Write-Host "Deploying DS-EO agent prompts to: $TargetDir"
Write-Host ""

$deployed = 0; $overwritten = 0

foreach ($af in $AgentFiles) {
    $src = "$AgentsSrc\$af"
    $dst = "$TargetDir\$af"

    if (-not (Test-Path $src)) {
        Write-Host "  [✗] Source not found: $src (skipping)"
        continue
    }

    if (Test-Path $dst) {
        Copy-Item $dst "${dst}.ds-eo-bak" -Force
        $overwritten++
        Write-Host "  [✓] Overwritten: $af (backup: ${dst}.ds-eo-bak)"
    } else {
        $deployed++
        Write-Host "  [✓] Deployed: $af"
    }

    Copy-Item $src $dst -Force
}

Write-Host ""
Write-Host "Agent prompt deployment complete:"
Write-Host "  Deployed:   $deployed new files"
Write-Host "  Overwritten: $overwritten existing files (backed up with .ds-eo-bak)"
