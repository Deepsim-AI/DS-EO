#!/usr/bin/env bash
# generate_openclaw_config.sh — Generate and/or merge DS-EO agent config entries
# Usage:
#   generate_openclaw_config.sh --generate [--workspace <path>]
#   generate_openclaw_config.sh --merge <agents_list.json>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENCLAW_DIR="${DS_EO_OPENCLAW_DIR:-$HOME/.openclaw}"
CONFIG_FILE="${DS_EO_CONFIG_FILE:-$OPENCLAW_DIR/openclaw.json}"
# ─── Generate Mode ────────────────────────────────────────────────

if [[ "${1:-}" == "--generate" ]]; then
    WORKSPACE="${2:-/home/deepsim/agent_system}"

    echo "DS-EO Agent Configuration Generator"
    echo ""
    echo "Enter model names for each role (press Enter for default):"
    echo ""

    # CTO Model
    read -r -p "  CTO model [ollama/qwen3.6:35b]: " cto_model
    cto_model="${cto_model:-ollama/qwen3.6:35b}"

    # Implementer Model
    read -r -p "  Implementer model [ollama/ornith:35b]: " impl_model
    impl_model="${impl_model:-ollama/ornith:35b}"

    # Reviewer Model
    read -r -p "  Reviewer model [ollama/laguna-xs-2.1:q4_K_M]: " rev_model
    rev_model="${rev_model:-ollama/laguna-xs-2.1:q4_K_M}"

    # PM Model
    read -r -p "  PM model [ollama/qwen3.6:35b]: " pm_model
    pm_model="${pm_model:-ollama/qwen3.6:35b}"

    echo ""
    echo "Workspace path: $WORKSPACE"
    echo ""

    # Verify models exist (if using ollama)
    if [[ "$cto_model" == ollama/* ]] || [[ "$impl_model" == ollama/* ]] || [[ "$rev_model" == ollama/* ]]; then
        echo "Checking Ollama model availability..."
        if command -v ollama &>/dev/null; then
            for model in "$cto_model" "$impl_model" "$rev_model" "$pm_model"; do
                if ollama list 2>/dev/null | grep -q "$(basename "$model")"; then
                    echo "  ✓ $model — available"
                else
                    echo "  ⚠ $model — not found in 'ollama list'"
                fi
            done
        else
            echo "  (Ollama CLI not found; skipping availability check)"
        fi
    fi

    # Generate agents_list.json using Python for proper JSON formatting
    python3 -c "
import json, sys

agents = [
    {
        'default': True,
        'id': 'cto',
        'name': 'CTO / Architect',
        'identity': {'emoji': '\U0001f3d7\ufe0f', 'name': 'CTO'},
        'model': sys.argv[1],
        'workspace': sys.argv[5],
        'tools': {
            'allow': ['group:fs','web_search','web_fetch','sessions_list','session_status','memory_search','memory_get','exec','process'],
            'deny': ['write','edit','apply_patch']
        }
    },
    {
        'default': False,
        'id': 'implementer',
        'name': 'Code Implementer',
        'identity': {'emoji': '\U0001f4bb', 'name': 'Implementer'},
        'model': sys.argv[2],
        'workspace': sys.argv[5],
        'tools': {
            'allow': ['group:fs','group:runtime','group:web','group:sessions','group:memory'],
            'profile': 'coding'
        }
    },
    {
        'default': False,
        'id': 'reviewer',
        'name': 'Senior Code Reviewer',
        'identity': {'emoji': '\U0001f50d', 'name': 'Reviewer'},
        'model': sys.argv[3],
        'workspace': sys.argv[5],
        'tools': {
            'allow': ['group:fs','web_search','web_fetch','exec','process','sessions_list','session_status','memory_search','memory_get'],
            'deny': ['write','edit','apply_patch']
        }
    },
    {
        'default': False,
        'id': 'pm',
        'name': 'Project Manager',
        'identity': {'emoji': '\U0001f4cb', 'name': 'PM'},
        'model': sys.argv[4],
        'workspace': sys.argv[5],
        'tools': {
            'allow': ['group:fs','web_search','web_fetch'],
            'deny': ['write','edit','apply_patch','exec','process']
        }
    }
]

output = json.dumps(agents, indent=2)
sys.stdout.write(output + '\n')
" "$cto_model" "$impl_model" "$rev_model" "$pm_model" "$WORKSPACE" > "$PKG_ROOT/agents_list.json"

    echo "✓ Agent config written to: $PKG_ROOT/agents_list.json"
    echo ""
    echo "  To merge into openclaw.json, run:"
    echo "    bash scripts/generate_openclaw_config.sh --merge agents_list.json"

    exit 0
fi

# ─── Merge Mode ────────────────────────────────────────────────────

if [[ "${1:-}" == "--merge" ]]; then
    AGENTS_FILE="${2:?Usage: generate_openclaw_config.sh --merge <agents_list.json>}"

    if [ ! -f "$AGENTS_FILE" ]; then
        echo "Error: $AGENTS_FILE not found"
        exit 1
    fi

    # ─── Pre-install conflict check ─────────────────────

    FORCE=false
    for arg in "${@}"; do
        if [[ "$arg" == "--force" ]]; then
            FORCE=true
        fi
    done

    echo "Running pre-install conflict check..."
    CONFLICT_RESULT=$($SCRIPT_DIR/conflict_check.sh "$CONFIG_FILE" 2>&1) && true
    local_conflict_exit=${PIPESTATUS[0]}

    if [[ $local_conflict_exit -ne 0 ]]; then
        echo "$CONFLICT_RESULT"
        echo ""
        if [[ "$FORCE" == false ]]; then
            echo "ERROR: Critical conflicts detected. Aborting merge." >&2
            echo ""
            echo "Resolution options:"
            echo "  1. Resolve conflicts manually, then re-run this command"
            echo "  2. Use --force to override (agents will be overwritten)"
            exit 1
        else
            echo "WARNING: --force specified — proceeding despite conflicts"
            # CONFLICT_RESULT already contains the full report above; skip re-printing
            echo ""
        fi
    else
        echo "OK: No critical conflicts detected"
    fi

    # ─── Perform the merge ──────────────────────────────

    python3 - "$CONFIG_FILE" "$AGENTS_FILE" <<'PYEOF'
import json, sys, os

config_path = sys.argv[1]
agents_file = sys.argv[2]

# Read existing config
with open(config_path, 'r') as f:
    config = json.load(f)

# Read new agents to merge
with open(agents_file, 'r') as f:
    ds_eo_agents = json.load(f)

# Preserve everything except 'agents' section
original_keys = {k: v for k, v in config.items() if k != 'agents'}

agents_section = config.get('agents', {})
defaults = agents_section.setdefault('defaults', {})
model_defaults = defaults.setdefault('model', {})

# Merge agents.list[] — replace existing IDs, append new ones
current_list = list(agents_section.get('list', []))
merged_list = list(current_list)
added_ds_eo_ids = set()

for agent in ds_eo_agents:
    agent_id = agent['id']
    if agent_id not in {a['id'] for a in current_list}:
        merged_list.append(agent)
        added_ds_eo_ids.add(agent_id)
    else:
        # Replace existing entry with same ID
        for i, existing in enumerate(merged_list):
            if existing.get('id') == agent_id:
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

    exit 0
fi

# ─── Default: Show Usage ──────────────────────────────────────────

echo "Usage:"
echo "  generate_openclaw_config.sh --generate [--workspace <path>]"
echo "  generate_openclaw_config.sh --merge <agents_list.json>"
exit 1
