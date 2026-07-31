# DS-EO Installation Guide — OpenClaw Edition

## Prerequisites

1. **OpenClaw** installed and running (minimum version: `2026.7.1`)
2. Access to `~/.openclaw/openclaw.json`
3. **Git** (optional, for the repository)
4. **Python 3** with `pyyaml` (`pip install pyyaml`) — needed for verification tests

## Installation Methods

### Method 1: Scripted Installation (Recommended)

```bash
# From this repository's root directory:
bash scripts/install.sh
```

The installer will walk you through each step interactively. It handles backup, config generation, merging, deployment, and verification automatically. If any verification check fails, it rolls back to the pre-install state.

### Method 2: Manual Installation (Step by Step)

If you prefer full control, follow these steps manually. Each step includes rollback instructions.

---

#### Pre-flight Checks

Before doing anything:
```bash
# Verify openclaw.json is valid JSON
python3 -c "import json; json.load(open('$HOME/.openclaw/openclaw.json'))" && echo "Config OK" || echo "Config INVALID — aborting"

# Check disk space (need >50MB free)
df -h ~/.openclaw/ | tail -1 | awk '{print $4}'

# Verify no existing DS-EO installation
grep -l "ds-eo-openclaw" ~/.openclaw/openclaw.json 2>/dev/null && echo "DS-EO already installed" || echo "Clean install"
```

---

#### Step 1: Backup Existing Config

```bash
# Create timestamped backup of openclaw.json
TIMESTAMP=$(date +%Y%m%dT%H%M%S)
mkdir -p ~/.openclaw/backups
cp ~/.openclaw/openclaw.json ~/.openclaw/backups/ds-eo-openclaw-${TIMESTAMP}.json.bak

# Verify backup exists
ls -la ~/.openclaw/backups/ds-eo-openclaw-*.json.bak | tail -1
```

**Rollback**: If anything goes wrong, restore: `cp ~/.openclaw/backups/ds-eo-openclaw-LATEST.json.bak ~/.openclaw/openclaw.json`

---

#### Step 2: Generate Agent Config Entries

The installer prompts for model names (defaults shown in brackets):

```bash
# Run the config generator interactively
bash scripts/generate_openclaw_config.sh --generate

# It will prompt you for:
│   CTO model name [ollama/qwen3.6:35b]: _your_input_or_enter_for_default_
│   Implementer model name [ollama/ornith:35b]: _your_input_or_enter_for_default_
│   Reviewer model name [ollama/laguna-xs-2.1:q4_K_M]: _your_input_or_enter_for_default_
│   Workspace path [/home/deepsim/agent_system]: _your_project_path_
# Output: agents_list.json (valid JSON array of 3 agent config objects)
```

**Manual alternative**: If you know the exact models, copy from `config-templates/example_openclaw_config.json` and adjust model names.

---

#### Step 3: Merge Agent Config into openclaw.json

```bash
# Merge the generated agents into your openclaw.json
bash scripts/generate_openclaw_config.sh --merge agents_list.json

# Verify the merge produced valid JSON
python3 -c "import json; json.load(open('$HOME/.openclaw/openclaw.json'))" && echo "JSON OK" || echo "JSON INVALID — rollback needed"

# Check that all 3 DS-EO agents are present
python3 -c "
import json
config = json.load(open('$HOME/.openclaw/openclaw.json'))
agents = [a['id'] for a in config.get('agents', {}).get('list', [])]
for role in ['cto', 'implementer', 'reviewer']:
    status = '✓' if role in agents else '✗ MISSING'
    print(f'{role}: {status}')
"
```

**Rollback**: `cp ~/.openclaw/backups/ds-eo-openclaw-LATEST.json.bak ~/.openclaw/openclaw.json`

---

#### Step 4: Deploy Protocol Files (Global)

```bash
# Deploy to global OpenClaw protocols directory
bash scripts/deploy_protocols.sh --target ~/.openclaw/protocols/
```

This copies all 7 protocol files (including GATE_AUTHORITY_MATRIX.md) from `ds-eo-openclaw/protocols/` to `~/.openclaw/protocols/`. Existing files are backed up with `.ds-eo-bak` suffix before overwriting.

---

#### Step 5: Deploy Protocol Files (Per-Project, Optional)

```bash
# Deploy to your project's development protocols directory
PROJECT_PATH="/path/to/your/project"
bash scripts/deploy_protocols.sh --target "${PROJECT_PATH}/docs/development/protocols/"
```

Skip this step if you only want global protocols. Multi-project setups benefit from deploying the same 7 protocol files per-project for customization.

---

#### Step 6: Deploy Agent Prompt Files (Per-Project)

```bash
# Deploy prompt files to your project workspace
PROJECT_PATH="/path/to/your/project"
bash scripts/deploy_agents.sh --target "${PROJECT_PATH}/docs/prompts/"
```

This copies `agents/*.md` to `<project>/docs/prompts/`, overwriting any existing CTO/Implementer/Reviewer prompts. Existing files are backed up with `.ds-eo-bak`.

---

#### Step 7: Verify Installation

```bash
# Run full verification suite
bash scripts/verify_installation.sh

# Or run individual checks:
python3 -m pytest tests/test_manifest_schema.py        # Manifest validation
python3 -m pytest tests/test_protocol_extraction.py    # Protocol completeness
python3 -m pytest tests/test_template_completeness.py  # Template sections
python3 -m pytest tests/test_config_merge_safety.py    # Config safety
bash tests/test_installation_flow.sh                    # End-to-end smoke test (on clean host)
```

If verification fails, the script automatically rolls back to your pre-install backup.

---

## Uninstallation

To remove DS-EO and restore original state:

```bash
# Restore from most recent backup
LATEST_BACKUP=$(ls -t ~/.openclaw/backups/ds-eo-openclaw-*.json.bak | head -1)
cp "$LATEST_BACKUP" ~/.openclaw/openclaw.json

# Remove DS-EO protocol files (optional — keeps .ds-eo-bak originals)
bash scripts/deploy_protocols.sh --rollback

# Clean up backup directory if desired
rm -rf ~/.openclaw/backups/ds-eo-openclaw-*
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `openclaw.json` is not valid JSON after merge | Rollback and check which step introduced the issue. Try manual merge with Python's json module. |
| Agent fails to start after install | Verify model names are correct (`ollama list`). Check that models exist on your host. |
| Protocol files conflict with existing versions | DS-EO overwrites global protocols. Per-project deployment is safer for custom setups. |
| Verification fails at Step 7 | Review error output — rollback was automatic. Fix the underlying issue and re-run installer. |
| "No backup found" during rollback | Ensure Step 1 (backup) completed successfully before proceeding. |

## Next Steps After Installation

1. **Restart OpenClaw** to load new agent configurations
2. **Verify agents appear** in your OpenClaw session list
3. **Create your first task**: Send an implementation request and watch the workflow execute
4. **Review the examples**: See `examples/minimal-workflow.md` for a walkthrough
