# conflict_check.ps1 — Check for agent config conflicts before installation (Windows)
# Usage: conflict_check.ps1 <config_file_path>

$ErrorActionPreference = "Stop"
$configFile = if ($Args.Count -ge 1) { $Args[0] } else { "$env:USERPROFILE\.openclaw\openclaw.json" }

if (-not (Test-Path $configFile)) {
    Write-Host "Config file not found: $configFile" -ForegroundColor Red
    exit 1
}

try {
    $config = Get-Content $configFile -Raw | ConvertFrom-Json
    $existingAgents = @(foreach ($a in $config.agents.list) { $a.id })
    $dsEoAgents = @('cto','implementer','reviewer','pm')
    
    $conflicts = @($dsEoAgents | Where-Object { $_ -in $existingAgents })
    
    if ($conflicts.Count -gt 0) {
        Write-Host "Conflicts detected:" -ForegroundColor Yellow
        foreach ($c in $conflicts) {
            Write-Host "  - Agent '$c' already exists (will be overwritten)" -ForegroundColor Gray
        }
        exit 1
    } else {
        Write-Host "No conflicts detected." -ForegroundColor Green
        exit 0
    }
} catch {
    Write-Host "Error reading config: $_" -ForegroundColor Red
    exit 1
}
