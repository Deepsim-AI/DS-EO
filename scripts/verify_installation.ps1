# verify_installation.ps1 — Post-install verification checks for Windows
# Runs all validation checks and reports results.
# Returns 0 on success, 1 on failure.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PkgRoot = (Get-Item $ScriptDir\..).FullName
$HomeEnv = if ($env:DS_EO_OPENCLAW_DIR) { $env:DS_EO_OPENCLAW_DIR } else { "$env:USERPROFILE\.openclaw" }
$configFile = if ($env:DS_EO_CONFIG_FILE) { $env:DS_EO_CONFIG_FILE } else { "$HomeEnv\openclaw.json" }
$backupDir = "$HomeEnv\backups"

$passCount = 0
$failCount = 0

function Check-Pass {
    param([string]$msg)
    Write-Host "  ✓ $msg" -ForegroundColor Green
    $script:passCount++
}

function Check-Fail {
    param([string]$msg)
    Write-Host "  ✗ $msg" -ForegroundColor Red
    $script:failCount++
}

Write-Host "DS-EO Installation Verification" -ForegroundColor Cyan
Write-Host ( "=" * 40 )
Write-Host ""

# ─── Check 1: openclaw.json is valid JSON ────────────────

$invalidJSON = $false
try {
    $json = Get-Content $configFile -Raw | ConvertFrom-Json
} catch {
    $invalidJSON = $true
}

if (-not $invalidJSON) {
    Check-Pass "openclaw.json is valid JSON"
} else {
    Check-Fail "openclaw.json is NOT valid JSON — rollback required"
}

# ─── Check 2: All 4 DS-EO agents present in config ───────

$agentsOK = $false
try {
    if (-not $invalidJSON) {
        $config = Get-Content $configFile -Raw | ConvertFrom-Json
        $agentIds = $config.agents.list.id
        $required = @('cto','implementer','pm','reviewer')
        $missing = @($required | Where-Object { $_ -notin $agentIds })
        if ($missing.Count -eq 0) {
            Check-Pass "All 4 DS-EO agents present in openclaw.json"
            $agentsOK = $true
        } else {
            Check-Fail "Missing DS-EO agents: $($missing -join ', ') — rollback required"
        }
    }
} catch {
    Check-Fail "Could not verify agent presence (config error)"
}

# ─── Check 3: Agent config completeness ──────────────────

if ($agentsOK) {
    try {
        $errors = @()
        foreach ($agent in $config.agents.list) {
            $aid = $agent.id
            foreach ($field in @('id','name','model','workspace')) {
                if (-not $agent.PSObject.Properties[$field] -or -not $agent.$field) {
                    $errors += "Agent $aid missing field: $field"
                }
            }
        }
        $ids = @(foreach ($a in $config.agents.list) { $a.id })
        if (($ids | Select-Object -Unique).Count -ne $ids.Count) {
            $errors += "Duplicate agent IDs found in agents.list[]"
        }
        if ($errors.Count -eq 0) {
            Check-Pass "Agent config entries are complete and valid"
        } else {
            foreach ($e in $errors) {
                Write-Host "    ERROR: $e" -ForegroundColor Red
            }
            Check-Fail "Agent config validation failed — rollback required"
        }
    } catch {
        Check-Fail "Agent config validation failed — rollback required"
    }
}

# ─── Check 4: Protocol files present (global) ────────────

$protoNames = @(
    'approval_protocol'
    'communication_protocol'
    'completion_protocol'
    'delegation_protocol'
    'handoff_protocol'
    'review_protocol'
)
$PROTO_MISSING = 0

foreach ($proto in $protoNames) {
    $protoFile = "$HomeEnv\protocols\$proto.md"
    if (Test-Path $protoFile) {
        $size = (Get-Item $protoFile).Length
        if ($size -lt 100) {
            Check-Fail "Protocol $proto.md is too small (${size} bytes) — may be truncated"
            $PROTO_MISSING++
        } else {
            Check-Pass "Global protocol present: $proto.md"
        }
    } else {
        Check-Fail "Global protocol missing: $HomeEnv\protocols\$proto.md"
        $PROTO_MISSING++
    }
}

if ($PROTO_MISSING -eq 0) {
    Check-Pass "All 6 DS-EO protocols present at global location (>100 bytes each)"
}

# ─── Check 5: Manifest file present and valid YAML ───────

$manifest = "$PkgRoot\ds_eo_manifest.yaml"
if (Test-Path $manifest) {
    try {
        # Use Python to validate YAML since PowerShell has no native YAML parser
        $result = python3 -c "import yaml; yaml.safe_load(open(r'$manifest'))" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Check-Pass "ds_eo_manifest.yaml is valid YAML"
        } else {
            Check-Fail "ds_eo_manifest.yaml is NOT valid YAML"
        }
    } catch {
        # Python not available or yaml module missing — best effort check
        if ((Get-Item $manifest).Length -gt 0) {
            Check-Pass "ds_eo_manifest.yaml present (Python YAML validation skipped)"
        } else {
            Check-Fail "ds_eo_manifest.yaml is empty"
        }
    }
} else {
    Check-Fail "ds_eo_manifest.yaml not found in package root"
}

# ─── Check 6: All agent prompt files present in package ──

$agentFiles = @('cto.md','implementer.md','pm.md','reviewer.md')
$agentsOK2 = $true

foreach ($af in $agentFiles) {
    $agentPath = "$PkgRoot\agents\$af"
    if (Test-Path $agentPath) {
        $size = (Get-Item $agentPath).Length
        if ($size -lt 100) {
            Check-Fail "Agent prompt $af is too small (${size} bytes)"
            $agentsOK2 = $false
        } else {
            Check-Pass "Agent prompt present: $af"
        }
    } else {
        Check-Fail "Agent prompt missing: agents\$af"
        $agentsOK2 = $false
    }
}

if ($agentsOK2) {
    Check-Pass "All 4 agent prompts present and non-empty in package"
}

# ─── Check 7: All template files present ─────────────────

$templateFiles = @(
    'task.md'
    'report_template.md'
    'review_report_template.md'
    'spec_template.md'
    'cto_approval_template.md'
)
$templatesOK = $true

foreach ($tf in $templateFiles) {
    $tmplPath = "$PkgRoot\templates\$tf"
    if (-not (Test-Path $tmplPath)) {
        Check-Fail "Template missing: templates\$tf"
        $templatesOK = $false
    } else {
        Check-Pass "Template present: $tf"
    }
}

if ($templatesOK) {
    Check-Pass "All 5 templates present in package"
}

# ─── Summary ─────────────────────────────────────────────

Write-Host ""
Write-Host ( "=" * 40 ) -ForegroundColor Cyan
$passColor = if ($failCount -gt 0) { 'Red' } else { 'Green' }
Write-Host "Results: $passCount passed, $failCount failed" -ForegroundColor $passColor
Write-Host ( "=" * 40 )

if ($failCount -gt 0) {
    Write-Host ""
    Write-Host "CRITICAL: Verification failed. Rollback recommended." -ForegroundColor Red
    $latestBackup = Get-ChildItem "$backupDir\ds-eo-openclaw-*.json.bak" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latestBackup) {
        Write-Host ""
        Write-Host "To rollback, run:" -ForegroundColor Yellow
        Write-Host "  Copy '$($latestBackup.FullName)' to '$configFile'" -ForegroundColor White
    } else {
        Write-Host ""
        Write-Host "No backup found. Manual intervention required." -ForegroundColor Yellow
    }
    exit 1
} else {
    Write-Host ""
    Write-Host "All verification checks passed. Installation is valid." -ForegroundColor Green
    exit 0
}
