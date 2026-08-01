# uninstall.ps1 — Clean removal of DS-EO OpenClaw Edition from a host (Windows)
#
# Usage:
#   uninstall.ps1 [-Confirm]                      # Non-interactive, auto-confirm all steps
#   uninstall.ps1 -DryRun                         # Show what would be removed without applying changes
#   uninstall.ps1 [-PurgeBackups]                 # Also remove backup files (use with caution)
#
# What it removes:
#   1. DS-EO agent entries from openclaw.json (restored byte-for-byte from backup)
#   2. Protocol files deployed to ~/.openclaw/protocols/ (.ds-eo-bak backups restored)
#   3. Agent prompt files deployed by DS-EO install
#   4. Protocol copies in project-level docs/development/protocols/
#
# Safety:
#   - Always preserves openclaw.json.bak.ds-eo-selfhost (or falls back to .bak)
#   - Never deletes backups unless explicitly asked with -PurgeBackups
#   - Dry-run mode shows exact changes without applying

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PkgRoot = (Get-Item "$ScriptDir\..").FullName
$HomeEnv = if ($env:DS_EO_OPENCLAW_DIR) { $env:DS_EO_OPENCLAW_DIR } else { "$env:USERPROFILE\.openclaw" }
$configFile = if ($env:DS_EO_CONFIG_FILE) { $env:DS_EO_CONFIG_FILE } else { "$HomeEnv\openclaw.json" }

# DS-EO known agent IDs and protocol files
$agentIds = @('cto','implementer','reviewer')
$dsEoProtocols = @(
    'approval_protocol.md'
    'communication_protocol.md'
    'completion_protocol.md'
    'delegation_protocol.md'
    'handoff_protocol.md'
    'review_protocol.md'
)

# Flags
$DryRun     = $false
$Confirm     = $false
$PurgeBackups = $false

foreach ($arg in $args) {
    switch ($arg.ToLower()) {
        '-confirm'      { $Confirm = $true }
        '-dryrun'       { $DryRun = $true; $Confirm = $true }
        '-purgebackups' { $PurgeBackups = $true; $Confirm = $true }
        default         { Write-Host "Unknown option: $arg" -ForegroundColor Red; exit 2 }
    }
}

if (-not $Confirm) {
    Write-Host ""
    $answer = Read-Host "Proceed with uninstall? [y/N]"
    if ($answer -notmatch '^[Yy]$') {
        Write-Host "[DS-EO Uninstall] Aborted by user." -ForegroundColor Cyan
        exit 0
    }
}

function Log  { Write-Host "[DS-EO Uninstall] $_" -ForegroundColor Cyan; }
function Ok   { Write-Host "  [✓] $_" -ForegroundColor Green; }
function Warn { Write-Host "  [⚠] $_" -ForegroundColor Yellow; }
function Err  { Write-Host "  [✗] $_" -ForegroundColor Red; }
function Info { Write-Host "=== $_ ===" -ForegroundColor White; }

# ─── Pre-flight Checks ─────────────────────

if (-not (Test-Path $configFile)) {
    Err "openclaw.json not found at $configFile"
    Write-Host "  Nothing to uninstall — DS-EO agents were never installed here."
    exit 0
}

# Find the best backup file (priority order)
function Find-Backup {
    $candidates = @(
        "$HomeEnv\openclaw.json.bak.ds-eo-selfhost",
        "$HomeEnv\openclaw.json.bak",
        "$HomeEnv\backups\ds-eo-openclaw-*.json.bak"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    # Check glob pattern for tar-backed backups
    $latestTar = Get-ChildItem "$HomeEnv\backups\ds-eo-openclaw-"*.json.bak -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latestTar) { return $latestTar.FullName }
    return $null
}

$backupFile = Find-Backup

if (-not $backupFile) {
    Err "No DS-EO backup found for openclaw.json restoration."
    Write-Host ""
    Write-Host "  Without a backup, I cannot safely restore your original configuration." -ForegroundColor Red
    Write-Host "  Options:"
    Write-Host "    1. Manually remove the DS-EO agents from $configFile"
    Write-Host "    2. Restore openclaw.json from another backup you may have"
    Write-Host "    3. Reinstall DS-EO, then run this script again to properly uninstall"
    exit 1
}

Ok "Backup found: $backupFile"
Write-Host ""

# ─── Step 1/4: Restore openclaw.json from backup ──────────────

Info "Step 1/4: Restoring openclaw.json"
Write-Host ""

if ($DryRun) {
    Log "[dry-run] Would restore $configFile from $backupFile"
} else {
    Copy-Item $backupFile $configFile -Force
    Ok "openclaw.json restored from backup ($backupFile)"

    # Verify byte-for-byte match using Python
    $result = python3 -c "
import sys, filecmp
sys.exit(0 if filecmp.cmp(sys.argv[1], sys.argv[2]) else 1)
" "$backupFile" "$configFile" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Ok "Verification: openclaw.json matches backup byte-for-byte ✓"
    } else {
        Err "WARNING: Restored file does NOT match backup!"
        Write-Host "  You should investigate the difference before restarting OpenClaw."
    }
}

# ─── Step 2/4: Remove global protocol files from ~/.openclaw/protocols/ ─

Info "Step 2/4: Removing global protocol files"
Write-Host ""

$protocolsDir = "$HomeEnv\protocols\"

if (Test-Path $protocolsDir) {
    foreach ($proto in $dsEoProtocols) {
        $protoPath = "$protocolsDir\$proto"
        if (Test-Path $protoPath) {
            $bakPath = "${protoPath}.ds-eo-bak"
            if (Test-Path $bakPath -and -not $DryRun) {
                Copy-Item $bakPath $protoPath -Force
                Remove-Item "$bakPath" -ErrorAction SilentlyContinue
                Ok "Restored $proto (from .ds-eo-bak backup)"
            } elseif ($DryRun) {
                Log "[dry-run] Would restore $proto from ${proto}.ds-eo-bak or remove if no backup exists"
            } else {
                Warn "${proto} — no .ds-eo-bak backup found; removing deployed version"
            }
        }
    }

    # Check for any remaining DS-EO marker files
    $remaining = Get-ChildItem "$protocolsDir*.ds-eo-bak" -ErrorAction SilentlyContinue
    if ($remaining) {
        Log "Cleaning up leftover DS-EO backup markers:"
        foreach ($f in $remaining) {
            if ($DryRun) {
                Log "[dry-run] Would remove $($f.FullName)"
            } else {
                Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
                Ok "Removed $($f.Name)"
            }
        }
    }
} else {
    Warn "Protocols directory not found — nothing to clean."
}

# ─── Step 3/4: Remove project-level protocol copies ──────────

Info "Step 3/4: Removing project-level protocol copies"
Write-Host ""

$projectProtocolsDir = "$PkgRoot\docs\development\protocols\"

if (Test-Path $projectProtocolsDir) {
    foreach ($proto in $dsEoProtocols) {
        $protoPath = "$projectProtocolsDir\$proto"
        if (Test-Path $protoPath) {
            if ($DryRun) {
                Log "[dry-run] Would remove $proto from project protocols dir"
            } else {
                Remove-Item $protoPath -Force -ErrorAction SilentlyContinue
                Ok "Removed $proto from project protocols dir"
            }
        }
    }

    # Remove README if it was added by DS-EO install
    $readmePath = "$projectProtocolsDir\README.md"
    if (Test-Path $readmePath) {
        $content = Get-Content $readmePath -Raw
        if ($content -match 'DS-EO|ds-eo-openclaw') {
            if ($DryRun) {
                Log "[dry-run] Would remove $readmePath (DS-EO generated)"
            } else {
                Remove-Item $readmePath -Force -ErrorAction SilentlyContinue
                Ok "Removed DS-EO README from project protocols dir"
            }
        }
    }
} else {
    Warn "Project protocols directory not found — nothing to clean."
}

# ─── Step 4/4: Remove agent prompt files ──────────────────────

Info "Step 4/4: Removing agent prompt files"
Write-Host ""

$agentPromptsDir = "$PkgRoot\docs\prompts\"
$promptFiles = @('ctos.md','implementer.md','reviewer.md')

if (Test-Path $agentPromptsDir) {
    foreach ($prompt in $promptFiles) {
        $promptPath = "$agentPromptsDir\$prompt"
        if (Test-Path $promptPath) {
            $content = Get-Content $promptPath -Raw
            if ($content -match 'DS-EO|ds-eo-openclaw') {
                if ($DryRun) {
                    Log "[dry-run] Would remove $prompt (DS-EO generated)"
                } else {
                    Remove-Item $promptPath -Force -ErrorAction SilentlyContinue
                    Ok "Removed DS-EO prompt: $prompt"
                }
            } else {
                Warn "$prompt exists but is not a DS-EO file — leaving it alone"
            }
        }
    }
} else {
    Warn "Agent prompts directory not found — nothing to clean."
}

# ─── Cleanup (optional) ──────────────────────────────────────

if ($PurgeBackups) {
    Info "Cleanup: Removing DS-EO backup files"
    Write-Host ""

    $backupPaths = @(
        "$HomeEnv\openclaw.json.bak.ds-eo-selfhost",
        "$HomeEnv\backups\ds-eo-openclaw-"*.json.bak
    )

    foreach ($bak in $backupPaths) {
        $matches = Get-ChildItem $bak -ErrorAction SilentlyContinue
        if ($matches) {
            foreach ($m in $matches) {
                if ($DryRun) {
                    Log "[dry-run] Would remove $($m.FullName)"
                } else {
                    Remove-Item $m.FullName -Force -ErrorAction SilentlyContinue
                    Ok "Removed backup: $($m.Name)"
                }
            }
        }
    }
}

# ─── Final Summary ──────────────────────────────────────────

Write-Host ""
if ($DryRun) {
    Info "Dry Run Complete"
    Write-Host "  No changes were made. The above shows what would be removed."
} else {
    Info "Uninstall Complete"
    Write-Host ""
    Write-Host "  openclaw.json has been restored from backup." -ForegroundColor Green
    Write-Host "  DS-EO protocol files have been cleaned up." -ForegroundColor Green
    Write-Host ""

    if (-not $PurgeBackups) {
        Warn "Backup files preserved. To remove them, run with -PurgeBackups:"
        Write-Host "  powershell -ExecutionPolicy Bypass -File $($MyInvocation.MyCommand.Name) -Confirm -PurgeBackups"
    }

    Write-Host ""
    Write-Host "  Next steps:" -ForegroundColor Cyan
    Write-Host "    1. Restart OpenClaw: openclaw gateway restart" -ForegroundColor Gray
    Write-Host "    2. Verify agents removed: python3 -c `"import json; d=json.load(open(r'$configFile')); print(len(d.get('agents',{}).get('list',[])))`"" -ForegroundColor Gray
    Write-Host "    3. (Optional) Remove this package: Remove-Item -Recurse -Force $PkgRoot" -ForegroundColor Gray
}

exit 0
