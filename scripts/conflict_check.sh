#!/usr/bin/env bash
# conflict_check.sh — Pre-install agent ID collision detection
#
# Usage:
#   conflict_check.sh <openclaw_config_path> [--json]
#
# Checks for conflicts between DS-EO agent definitions and existing agents:
#   1. Do any existing agents share IDs with DS-EO (cto, implementer, reviewer)?
#   2. Are there duplicate agent names in the config?
#   3. Does the host have a compatible OpenClaw version?
#
# Exit codes:
#   0 — No conflicts detected (safe to proceed)
#   1 — Conflicts found (requires --force or manual resolution)
#   2 — Invalid usage / bad arguments

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# DS-EO agent definitions (source of truth for this package)
DS_EO_AGENTS=(
    "cto:CTO / Architect:ollama/qwen3.6:35b"
    "implementer:Code Implementer:ollama/ornith:35b"
    "reviewer:Senior Code Reviewer:ollama/laguna-xs-2.1:q4_K_M"
)

OUTPUT_JSON=false

# ─── Argument Parsing ──────────────────────────────────────────────

if [[ "${1:-}" == "--json" ]]; then
    OUTPUT_JSON=true
    shift
fi

if [[ $# -lt 1 ]] || [[ ! -f "$1" ]]; then
    echo "Usage: conflict_check.sh [--json] <openclaw_config_path>" >&2
    exit 2
fi

CONFIG_FILE="$1"

# ─── Helpers ──────────────────────────────────────────────────────

declare -a conflicts=()
declare -a warnings_list=()
critical_count=0
warning_count=0

add_conflict() {
    local severity="$1"
    local message="$2"
    if [[ "$severity" == "CRITICAL" ]]; then
        critical_count=$((critical_count + 1))
    else
        warning_count=$((warning_count + 1))
    fi
    conflicts+=("${severity}|${message}")
}

add_warning() {
    local message="$1"
    warning_count=$((warning_count + 1))
    warnings_list+=("$message")
}

# ─── Check 1: Agent ID Conflicts ────────────────────────────────

check_id_conflicts() {
    if [[ "$OUTPUT_JSON" == true ]]; then
        echo '{"section":"agent_id_conflicts","status":"checking"}'
    else
        echo ""
        echo "--- Check 1: Agent ID Conflicts ---"
    fi

    local config_agents
    config_agents=$(python3 -c "
import json, sys

try:
    with open('$CONFIG_FILE') as f:
        data = json.load(f)
except (json.JSONDecodeError, FileNotFoundError) as e:
    print(f'ERROR:{e}')
    sys.exit(1)

agents = data.get('agents', {}).get('list', [])
for a in agents:
    aid = a.get('id', 'unknown')
    name = a.get('name', 'unnamed')
    model = a.get('model', 'none')
    print(f'{aid}|{name}|{model}')
" 2>&1) || { echo "ERROR: Could not parse config file"; exit 2; }

    if [[ "$config_agents" == ERROR:* ]]; then
        add_conflict "CRITICAL" "Cannot parse $CONFIG_FILE: ${config_agents#ERROR:}"
        return
    fi

    for ds_eo_entry in "${DS_EO_AGENTS[@]}"; do
        IFS=':' read -r ds_id ds_name ds_model <<< "$ds_eo_entry"

        # Search existing agents for matching ID
        while IFS='|' read -r existing_id existing_name existing_model; do
            if [[ "$existing_id" == "$ds_id" ]]; then
                # Check if definitions match (same name and model = compatible)
                if [[ "$existing_name" == "$ds_name" && "$existing_model" == "$ds_model" ]]; then
                    # Compatible — same agent, different deployment. Not a conflict.
                    if [[ "$OUTPUT_JSON" == false ]]; then
                        echo "  ✓ ID '$ds_id' matches DS-EO definition (compatible)"
                    fi
                else
                    add_conflict "CRITICAL" \
                        "Agent ID '$ds_id' already exists with different definition: name='$existing_name', model='$existing_model'"
                    if [[ "$OUTPUT_JSON" == false ]]; then
                        echo "  ✗ CONFLICT: Agent ID '$ds_id' already in use by a different agent"
                        echo "    Existing : $existing_name ($existing_model)"
                        echo "    DS-EO    : $ds_name ($ds_model)"
                    fi
                fi
            fi
        done <<< "$config_agents"
    done

    if [[ ${#conflicts[@]} -eq 0 ]]; then
        if [[ "$OUTPUT_JSON" == false ]]; then
            echo "  ✓ No agent ID conflicts detected"
        fi
    fi
}

# ─── Check 2: Duplicate Agent Names ──────────────────────────────

check_duplicate_names() {
    local config_agents
    config_agents=$(python3 -c "
import json, sys
with open('$CONFIG_FILE') as f:
    data = json.load(f)
agents = data.get('agents', {}).get('list', [])
for a in agents:
    aid = a.get('id', 'unknown')
    name = a.get('name', 'unnamed')
    print(f'{aid}|{name}')
" 2>&1) || return

    # Check for duplicate names (not IDs — names can be unique even with same ID)
    local seen_names=()
    while IFS='|' read -r aid name; do
        for seen in "${seen_names[@]:-}"; do
            if [[ "$seen" == "$name" ]]; then
                add_conflict "WARNING" "Duplicate agent name: '$name'"
                break
            fi
        done
        seen_names+=("$name")
    done <<< "$config_agents"

    # Also check for empty/blank IDs (structural issue)
    while IFS='|' read -r aid name; do
        if [[ -z "$aid" || "$aid" == "unknown" ]]; then
            add_conflict "WARNING" "Agent missing ID field (name: '$name')"
        fi
    done <<< "$config_agents"

    if [[ $warning_count -eq 0 ]]; then
        if [[ "$OUTPUT_JSON" == false ]]; then
            echo "--- Check 2: Duplicate Names ---"
            echo "  ✓ No duplicate names detected"
        fi
    fi
}

# ─── Check 3: OpenClaw Version Compatibility ──────────────────────

check_version() {
    local config_agents
    config_agents=$(python3 -c "
import json, sys
with open('$CONFIG_FILE') as f:
    data = json.load(f)
defaults = data.get('agents', {}).get('defaults', {})
# Check for model field in defaults (used by DS-EO)
print(defaults.get('model', {}).get('primary', ''))
" 2>&1) || return

    if [[ "$OUTPUT_JSON" == false ]]; then
        echo "--- Check 3: Compatibility ---"
    fi

    # Check if config has the structure DS-EO expects (agents.list with proper fields)
    local has_list
    has_list=$(python3 -c "
import json, sys
with open('$CONFIG_FILE') as f:
    data = json.load(f)
print('yes' if 'list' in data.get('agents', {}) else 'no')
" 2>&1) || return

    if [[ "$has_list" == "no" ]]; then
        add_conflict "WARNING" "Config structure may be incompatible — no agents.list found"
    fi

    # Check for very old config format (pre-v0.5 OpenClaw used different structure)
    local has_tools_field
    has_tools_field=$(python3 -c "
import json, sys
with open('$CONFIG_FILE') as f:
    data = json.load(f)
agents = data.get('agents', {}).get('list', [])
has_tools = any('tools' in a for a in agents if isinstance(a, dict))
print('yes' if has_tools else 'no')
" 2>&1) || return

    # This is informational — DS-EO requires tools field support
    if [[ "$OUTPUT_JSON" == false ]]; then
        echo "  ℹ Config has tools field support: $has_tools_field"
    fi
}

# ─── Main Execution ───────────────────────────────────────────────

if [[ "$OUTPUT_JSON" == true ]]; then
    echo '{"check":"conflict_check","config_file":"'${CONFIG_FILE}'"}'
fi

check_id_conflicts
check_duplicate_names
check_version

# ─── Summary ──────────────────────────────────────────────────────

if [[ "$OUTPUT_JSON" == true ]]; then
    echo "{"
    echo "  \"result\": \"$([ $critical_count -eq 0 ] && echo PASS || echo FAIL)\","
    echo "  \"critical_conflicts\": ${critical_count},"
    echo "  \"warnings\": ${warning_count}"

    if [[ ${#conflicts[@]} -gt 0 ]]; then
        echo "  \"conflicts\": ["
        local first=true
        for c in "${conflicts[@]}"; do
            IFS='|' read -r sev msg <<< "$c"
            if [[ "$first" == true ]]; then
                first=false
            else
                echo ","
            fi
            printf '    {"severity":"%s","message":"%s"}' "$sev" "$msg"
        done
        echo ""
        echo "  ]"
    fi
    echo "}"
else
    echo ""
    if [[ $critical_count -eq 0 ]]; then
        echo "═══ PASS: No critical conflicts detected ═══"
        if [[ ${#warnings_list[@]} -gt 0 ]]; then
            echo ""
            echo "Warnings:"
            for w in "${warnings_list[@]}"; do
                echo "  ⚠ $w"
            done
        fi
        exit 0
    else
        echo "═══ FAIL: ${critical_count} critical conflict(s) detected ═══"
        echo ""
        echo "Conflicts:"
        idx=1
        for c in "${conflicts[@]}"; do
            IFS='|' read -r sev msg <<< "$c"
            echo "  ${idx}. [${sev}] $msg"
            idx=$((idx + 1))
        done
        echo ""
        echo "Resolution options:"
        echo "  1. Remove conflicting agents from the existing config first"
        echo "  2. Use --force to override (agents will be overwritten)"
        echo "  3. Rename DS-EO agents during installation"
        exit 1
    fi
fi
