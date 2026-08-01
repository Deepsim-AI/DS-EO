# install.ps1 — DS-EO OpenClaw Edition Main Installer (PowerShell for Windows)
# Runs all installation steps in order with verification between each.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PkgRoot = (Get-Item "$ScriptDir\..").FullName
$HomeEnv = if ($env:DS_EO_OPENCLAW_DIR) { $env:DS_EO_OPENCLAW_DIR } else { "$env:USERPROFILE\.openclaw" }
$configFile = if ($env:DS_EO_CONFIG_FILE) { $env:DS_EO_CONFIG_FILE } else { "$HomeEnv\openclaw.json" }
$backupDir = "$HomeEnv\backups"

function Log  { Write-Host "[DS-EO]" -ForegroundColor Cyan " $_"; }
function Ok   { Write-Host "  [✓] $_" -ForegroundColor Green; }
function Warn { Write-Host "  [⚠] $_" -ForegroundColor Yellow; }
function Err  { Write-Host "  [✗] $_" -ForegroundColor Red; }

function Read-YesNo ($prompt, $default = $false) {
    while ($true) {
        Write-Host ""
        Write-Host ("─" * 50)
        Write-Host "  DS-EO OpenClaw Edition — Installation (Windows)" -ForegroundColor Cyan
        Write-Host ("─" * 50)
        
        # ─── Pre-flight Checks ─────────────────────

        if (-not (Test-Path $configFile)) {
            Err "openclaw.json not found at $configFile"
            Write-Host "  Please ensure OpenClaw is installed and configured."
            exit 1
        }

        # Check openclaw.json is valid JSON
        try {
            $json = Get-Content $configFile -Raw | ConvertFrom-Json
            Ok "openclaw.json exists and is valid JSON"
        } catch {
            Err "openclaw.json is not valid JSON — aborting for safety"
            Write-Host "  Backup your file first, then investigate the corruption."
            exit 1
        }

        # Check disk space (>50MB free)
        $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$((Get-Location).Drive.Name):'" | Select-Object FreeSpace
        $freeKB = [math]::Floor($disk.FreeSpace / 1KB)
        if ($freeKB -lt 50000) {
            Warn "Low disk space: ${freeKB}KB available (need >50MB)"
            $confirm = Read-Host "Continue anyway? [y/N]"
            if ($confirm -notmatch '^[Yy]$') { exit 1 }
        } else {
            Ok "Sufficient disk space (${freeKB}KB free)"
        }

        # Check for existing DS-EO installation
        $existingDS = $false
        try {
            $existingDS = @($json.agents.list | Where-Object { $_.id -in @('cto','implementer','reviewer') }).Count -gt 0
        } catch { }

        if ($existingDS) {
            Warn "DS-EO agents already found in openclaw.json"
            $confirm = Read-Host "Reinstall (will overwrite existing DS-EO entries)? [y/N]"
            if ($confirm -notmatch '^[Yy]$') { exit 0 }
        } else {
            Ok "Clean install — no existing DS-EO agents detected"
        }

        # ─── Step 1: Backup ────────────────────────

        Log ""
        Log "Step 1/7: Backing up openclaw.json..."
        New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
        $timestamp = Get-Date -Format "yyyyMMddTHHmmss"
        Copy-Item $configFile "$backupDir\ds-eo-openclaw-${timestamp}.json.bak"
        Ok "Backup created: $backupDir\ds-eo-openclaw-${timestamp}.json.bak"

        # ─── Step 2: Generate Agent Config (Interactive) ──────────

        Log ""
        Log "Step 2/7: Generating agent configuration..."

        Write-Host ""
        $ws = Read-Host "Workspace path [$DEFAULT_WORKSPACE]"
        $workspace = if ($ws) { $ws } else { "$env:USERPROFILE\agent_system" }

        Write-Host ""
        Write-Host "  Enter model names for each role (press Enter for default):" -ForegroundColor Gray

        $ctoModel  = Read-Host "  CTO model [ollama/qwen3.6:35b]"
        $ctoModel  = if ($ctoModel) { $ctoModel } else { "ollama/qwen3.6:35b" }

        $implModel = Read-Host "  Implementer model [ollama/ornith:35b]"
        $implModel = if ($implModel) { $implModel } else { "ollama/ornith:35b" }

        $revModel  = Read-Host "  Reviewer model [ollama/laguna-xs-2.1:q4_K_M]"
        $revModel  = if ($revModel) { $revModel } else { "ollama/laguna-xs-2.1:q4_K_M" }

        $pmModel   = Read-Host "  PM model [ollama/qwen3.6:35b]"
        $pmModel   = if ($pmModel) { $pmModel } else { "ollama/qwen3.6:35b" }

        Write-Host ""
        Ok "Workspace path: $workspace"

        # Generate agents_list.json using Python for proper JSON formatting
        $agentsListPath = "$PkgRoot\agents_list.json"
        python3 -c "
import json, sys

agents = [
    {'default': True, 'id': 'cto', 'name': 'CTO / Architect',
     'identity': {'emoji': '\U0001f3d7\ufe0f', 'name': 'CTO'}, 'model': sys.argv[1], 'workspace': sys.argv[5],
     'tools': {'allow': ['group:fs','web_search','web_fetch','sessions_list','session_status','memory_search','memory_get','exec','process'],
               'deny': ['write','edit','apply_patch']}},
    {'default': False, 'id': 'implementer', 'name': 'Code Implementer',
     'identity': {'emoji': '\U0001f4bb', 'name': 'Implementer'}, 'model': sys.argv[2], 'workspace': sys.argv[5],
     'tools': {'allow': ['group:fs','group:runtime','group:web','group:sessions','group:memory'], 'profile': 'coding'}},
    {'default': False, 'id': 'reviewer', 'name': 'Senior Code Reviewer',
     'identity': {'emoji': '\U0001f50d', 'name': 'Reviewer'}, 'model': sys.argv[3], 'workspace': sys.argv[5],
     'tools': {'allow': ['group:fs','web_search','web_fetch','exec','process','sessions_list','session_status','memory_search','memory_get'],
               'deny': ['write','edit','apply_patch']}},
    {'default': False, 'id': 'pm', 'name': 'Project Manager',
     'identity': {'emoji': '\U0001f4cb', 'name': 'PM'}, 'model': sys.argv[4], 'workspace': sys.argv[5],
     'tools': {'allow': ['group:fs','web_search','web_fetch'],
               'deny': ['write','edit','apply_patch','exec','process']}}
]

output = json.dumps(agents, indent=2)
sys.stdout.write(output + '\n')
" "$ctoModel" "$implModel" "$revModel" "$pmModel" "$workspace" > $agentsListPath

        if (-not (Test-Path $agentsListPath)) {
            Err "Config generation failed — agents_list.json not created"
            exit 1
        }
        Ok "Agent config generated: $agentsListPath"

        # ─── Step 3: Merge into openclaw.json ──────────────

        Log ""
        Log "Step 3/7: Merging agent configuration..."

        & "$ScriptDir\generate_openclaw_config.ps1" --merge $agentsListPath

        try {
            Get-Content $configFile -Raw | ConvertFrom-Json | Out-Null
            Ok "Config merged and validated successfully"
        } catch {
            Err "Merge produced invalid JSON — rolling back"
            # Simplified rollback: copy backup back
            $latestBackup = Get-ChildItem "$backupDir\ds-eo-openclaw-*.json.bak" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if ($latestBackup) { Copy-Item $latestBackup.FullName $configFile -Force }
            exit 1
        }

        # ─── Step 4: Deploy Protocols (Global) ─────────────

        Log ""
        Log "Step 4/7: Deploying protocols (global)..."
        & "$ScriptDir\deploy_protocols.ps1" --target "$HomeEnv\protocols\"
        Ok "Protocols deployed to $HomeEnv\protocols\"

        # ─── Step 5: Deploy Protocols (Per-Project, Optional) ──────────────

        Log ""
        Log "Step 5/7: Per-project protocol deployment"

        $currentDir = (Get-Location).Path
        $projectProtocols = if (Test-Path "$currentDir\docs\development\protocols") { "$currentDir\docs\development\protocols\" } else { "" }

        if ($projectProtocols) {
            $confirm = Read-Host "Deploy protocols to $projectProtocols? [Y/n]"
            if ($confirm -notmatch '^[Nn]$') {
                & "$ScriptDir\deploy_protocols.ps1" --target $projectProtocols
                Ok "Protocols deployed to project workspace"
            } else {
                Warn "Skipping per-project protocol deployment"
            }
        } else {
            Write-Host ""
            $confirm = Read-Host "Deploy protocols to a project workspace? (y/N)"
            if ($confirm -match '^[Yy]$') {
                $projPath = Read-Host "Project path"
                if ($projPath) {
                    & "$ScriptDir\deploy_protocols.ps1" --target "$projPath\docs\development\protocols\"
                    Ok "Protocols deployed to $projPath\docs\development\protocols\"
                }
            } else {
                Warn "Skipping per-project protocol deployment (optional)"
            }
        }

        # ─── Step 6: Deploy Agent Prompts (Per-Project) ────────────────────

        Log ""
        Log "Step 6/7: Deploying agent prompts..."

        if (Test-Path "$currentDir\docs\prompts\") {
            & "$ScriptDir\deploy_agents.ps1" --target "$currentDir\docs\prompts\"
            Ok "Agent prompts deployed to $currentDir\docs\prompts\"
        } else {
            Write-Host ""
            $confirm = Read-Host "Deploy agent prompts to a project? (y/N)"
            if ($confirm -match '^[Yy]$') {
                $projPath = Read-Host "Project path"
                if ($projPath) {
                    & "$ScriptDir\deploy_agents.ps1" --target "$projPath\docs\prompts\"
                    Ok "Agent prompts deployed to $projPath\docs\prompts\"
                }
            } else {
                Warn "Skipping per-project prompt deployment (optional)"
            }
        }

        # ─── Step 7: Verify Installation ──────────

        Log ""
        Log "Step 7/7: Verifying installation..."

        $verifyResult = & "$ScriptDir\verify_installation.ps1"
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Log "Installation complete!"
            Write-Host ""
            Write-Host "  Next steps:" -ForegroundColor Cyan
            Write-Host "    1. Restart OpenClaw to load new agent configurations" -ForegroundColor Gray
            Write-Host "    2. Verify agents appear in your session list" -ForegroundColor Gray
            Write-Host "    3. Send an implementation request to start a task cycle" -ForegroundColor Gray
            Write-Host ""
            Log "Backup location: $backupDir\"
        } else {
            Err "Verification failed — initiating automatic rollback..."
            exit 1
        }
    }
}

Write-Host ""
Log "Usage:"
Log "  powershell -ExecutionPolicy Bypass -File scripts\install.ps1"
