# deploy_protocols.ps1 — Deploy DS-EO protocol files to target location (Windows)
# Usage:
#   deploy_protocols.ps1 --target <path>           # Deploy protocols to target
#   deploy_protocols.ps1 --rollback [--target <path>]  # Remove DS-EO protocols

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PkgRoot = (Get-Item "$ScriptDir\..").FullName
$ProtosSrc = "$PkgRoot\protocols"

$ProtoFiles = @(
    'approval_protocol.md'
    'communication_protocol.md'
    'completion_protocol.md'
    'delegation_protocol.md'
    'handoff_protocol.md'
    'implementation_protocol.md'
    'release_management_protocol.md'
    'review_protocol.md'
)

if (-not $Args) {
    Write-Host "Usage:"
    Write-Host "  deploy_protocols.ps1 --target <path>     Deploy protocols to target directory"
    Write-Host "  deploy_protocols.ps1 --rollback          Remove DS-EO protocols, restore backups"
    exit 0
}

if ($Args[0] -eq "--rollback") {
    if ($Args.Count -ge 2 -and $Args[1] -eq "--target") {
        $TargetDir = $Args[2]
    } else {
        Write-Host "Error: Target directory required for rollback. Use --target <path>"
        exit 1
    }

    Write-Host "Rolling back DS-EO protocols from: $TargetDir"
    foreach ($proto in $ProtoFiles) {
        $targetFile = "$TargetDir\$proto"
        $backupFile = "${targetFile}.ds-eo-bak"
        if (Test-Path $backupFile) {
            Move-Item $backupFile $targetFile -Force
            Write-Host "  Restored: $targetFile (from .ds-eo-bak backup)"
        } elseif (Test-Path $targetFile) {
            Write-Host "  Removed:  $targetFile (no backup found — file was not from DS-EO install)"
        }
    }
    Write-Host "Rollback complete."
    exit 0
}

if ($Args[0] -eq "--target") {
    if ($Args.Count -lt 2) {
        Write-Host "Error: Target directory required. Use --target <path>"
        exit 1
    }
    $TargetDir = $Args[1]
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

    Write-Host "Deploying DS-EO protocols to: $TargetDir"
    Write-Host ""

    $deployed = 0; $overwritten = 0

    foreach ($proto in $ProtoFiles) {
        $src = "$ProtosSrc\$proto"
        $dst = "$TargetDir\$proto"
        if (-not (Test-Path $src)) {
            Write-Host "  [✗] Source not found: $src (skipping)"
            continue
        }
        if (Test-Path $dst) {
            Copy-Item $dst "${dst}.ds-eo-bak" -Force
            $overwritten++
            Write-Host "  [✓] Overwritten: $proto (backup: ${dst}.ds-eo-bak)"
        } else {
            $deployed++
            Write-Host "  [✓] Deployed: $proto"
        }
        Copy-Item $src $dst -Force
    }

    if (Test-Path "$ProtosSrc\README.md") {
        $dstReadme = "$TargetDir\README.md"
        if (-not (Test-Path $dstReadme)) {
            Copy-Item "$ProtosSrc\README.md" $dstReadme -Force
        }
    }

    Write-Host ""
    Write-Host "Deployment complete:"
    Write-Host "  Deployed:   $deployed new files"
    Write-Host "  Overwritten: $overwritten existing files (backed up with .ds-eo-bak)"
    exit 0
}

Write-Host "Usage:"
Write-Host "  deploy_protocols.ps1 --target <path>     Deploy protocols to target directory"
Write-Host "  deploy_protocols.ps1 --rollback          Remove DS-EO protocols, restore backups"
