# generate_openclaw_config.ps1 — Generate and/or merge DS-EO agent config entries (Windows)
# Usage:
#   generate_openclaw_config.ps1 --generate [--workspace <path>]
#   generate_openclaw_config.ps1 --merge <agents_list.json>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PkgRoot = (Get-Item "$ScriptDir\..").FullName
$HomeEnv = if ($env:DS_EO_OPENCLAW_DIR) { $env:DS_EO_OPENCLAW_DIR } else { "$env:USERPROFILE\.openclaw" }
$configFile = if ($env:DS_EO_CONFIG_FILE) { $env:DS_EO_CONFIG_FILE } else { "$HomeEnv\openclaw.json" }

if (-not $Args) {
    Write-Host "Usage:"
    Write-Host "  generate_openclaw_config.ps1 --generate [--workspace <path>]"
    Write-Host "  generate_openclaw_config.ps1 --merge <agents_list.json>"
    exit 0
}

if ($Args[0] -eq "--generate") {
    $defaultWorkspace = "$env:USERPROFILE\agent_system"
    $wsInput = Read-Host "Workspace path [$defaultWorkspace]"
    $workspace = if ($wsInput) { $wsInput } else { $defaultWorkspace }

    Write-Host ""
    Write-Host "Enter model names for each role (press Enter for default):" -ForegroundColor Gray
    Write-Host ""

    $ctoModel  = Read-Host "  CTO model [ollama/qwen3.6:35b]"
    if (-not $ctoModel) { $ctoModel = "ollama/qwen3.6:35b" }

    $implModel = Read-Host "  Implementer model [ollama/ornith:35b]"
    if (-not $implModel) { $implModel = "ollama/ornith:35b" }

    $revModel  = Read-Host "  Reviewer model [ollama/laguna-xs-2.1:q4_K_M]"
    if (-not $revModel) { $revModel = "ollama/laguna-xs-2.1:q4_K_M" }

    $pmModel   = Read-Host "  PM model [ollama/qwen3.6:35b]"
    if (-not $pmModel) { $pmModel = "ollama/qwen3.6:35b" }

    Write-Host ""
    Write-Host "Workspace path: $workspace" -ForegroundColor Gray

    # Verify models exist (if using ollama)
    if ($ctoModel -match '^ollama/' -or $implModel -match '^ollama/' -or $revModel -match '^ollama/') {
        Write-Host "Checking Ollama model availability..."
        if (Get-Command ollama -ErrorAction SilentlyContinue) {
            foreach ($model in @($ctoModel, $implModel, $revModel, $pmModel)) {
                $name = [System.IO.Path]::GetFileNameWithoutExtension($model)
                if (ollama list 2>&1 | Select-String -SimpleMatch "$name") {
                    Write-Host "  ✓ $model — available" -ForegroundColor Green
                } else {
                    Write-Host "  ⚠ $model — not found in 'ollama list'" -ForegroundColor Yellow
                }
            }
        } else {
            Write-Host "  (Ollama CLI not found; skipping availability check)"
        }
    }

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

    Write-Host "✓ Agent config written to: $agentsListPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "  To merge into openclaw.json, run:"
    Write-Host "    powershell -ExecutionPolicy Bypass -File scripts\generate_openclaw_config.ps1 --merge agents_list.json"
    exit 0
}

if ($Args[0] -eq "--merge") {
    if ($Args.Count -lt 2) { throw "Usage: generate_openclaw_config.ps1 --merge <agents_list.json>" }
    $agentsFile = $Args[1]

    if (-not (Test-Path $agentsFile)) {
        Write-Host "Error: $agentsFile not found" -ForegroundColor Red
        exit 1
    }

    # Run conflict check
    $conflictScript = "$ScriptDir\conflict_check.ps1"
    if (Test-Path $conflictScript) {
        Write-Host "Running pre-install conflict check..."
        & $conflictScript $configFile 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Critical conflicts detected. Aborting merge." -ForegroundColor Red
            Write-Host ""
            Write-Host "Resolution options:"
            Write-Host "  1. Resolve conflicts manually, then re-run this command"
            exit 1
        } else {
            Write-Host "OK: No critical conflicts detected" -ForegroundColor Green
        }
    }

    # Merge using Python (handles JSON properly)
    python3 - "$configFile" "$agentsFile" <<'PYEOF'
import json, sys, os

config_path = sys.argv[1]
agents_file = sys.argv[2]

with open(config_path, 'r') as f:
    config = json.load(f)

with open(agents_file, 'r') as f:
    ds_eo_agents = json.load(f)

original_keys = {k: v for k, v in config.items() if k != 'agents'}
agents_section = config.get('agents', {})
defaults = agents_section.setdefault('defaults', {})
model_defaults = defaults.setdefault('model', {})

current_list = list(agents_section.get('list', []))
merged_list = list(current_list)

for agent in ds_eo_agents:
    aid = agent['id']
    if aid not in [a['id'] for a in current_list]:
        merged_list.append(agent)
    else:
        for i, existing in enumerate(merged_list):
            if existing.get('id') == aid:
                merged_list[i] = agent
                break

default_model = model_defaults.get('primary', '')
if not default_model:
    default_model = ds_eo_agents[0]['model']
    model_defaults['primary'] = default_model

result = {**original_keys, 'agents': {'defaults': {'model': model_defaults}, 'list': merged_list}}

json_str = json.dumps(result, indent=2)
tmp_path = config_path + '.tmp'
with open(tmp_path, 'w') as f:
    f.write(json_str)
os.rename(tmp_path, config_path)
print('Merge complete. Config written to:', config_path)
PYEOF

    exit $LASTEXITCODE
}

Write-Host "Usage:"
Write-Host "  generate_openclaw_config.ps1 --generate [--workspace <path>]"
Write-Host "  generate_openclaw_config.ps1 --merge <agents_list.json>"
