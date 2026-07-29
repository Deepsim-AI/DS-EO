# Migration Guide — DS-AIOS to DS-EO OpenClaw Edition

## Overview

This guide walks through migrating from the current DS-AIOS development setup (scattered files in `agent_system/` and `~/.openclaw/`) to the packaged DS-EO OpenClaw Edition.

**Key principle**: DS-EO does not modify your existing DS-AIOS code or runtime agents. It extracts only the engineering organization components and packages them as an independent, installable unit.

## What Changes vs. What Stays

### Changes (Engineering Organization Extracted)

| Component | Before | After |
|-----------|--------|-------|
| Agent definitions | Scattered in `openclaw.json` + prompts/ | Packaged in `ds-eo-openclaw/agents/` with portable config generation |
| Protocols | Only at `~/.openclaw/protocols/` and project mirror | Packaged source of truth, deployed to both locations |
| Task workflow | Defined only in AGENTS.md | Defined in package protocols + templates for consistency |

### Stays the Same (DS-AIOS Runtime Unaffected)

- DS-AIOS source code (`app/`, `api/`, etc.) — untouched
- DS-AIOS runtime agents (CEO, Research, Writer) — untouched
- Your existing OpenClaw gateway/plugins/channels config — preserved by merge algorithm
- Any non-DS-EO agent configurations you've added — preserved

## Migration Steps

### 1. Review Current Setup

```bash
# See what DS-EO will extract
cat ~/agent_system/AGENTS.md | head -20
ls ~/.openclaw/protocols/
python3 -c "import json; print(json.dumps(json.load(open('$HOME/.openclaw/openclaw.json')).get('agents',{}), indent=2))"
```

### 2. Run DS-EO Installation

```bash
cd ds-eo-openclaw
bash scripts/install.sh
```

The installer:
1. Backs up your current `openclaw.json`
2. Generates portable agent configs (you choose model names)
3. Merges safely into your existing config
4. Deploys protocols globally and to your project
5. Verifies everything works

### 3. Verify Migration

```bash
# Check agents loaded correctly
openclaw status

# Or check the config directly
python3 -c "
import json
config = json.load(open('$HOME/.openclaw/openclaw.json'))
for agent in config['agents']['list']:
    print(f\"  {agent['id']}: {agent.get('name','?')} (model: {agent.get('model','?')})\")"
```

### 4. Test a Task Cycle

Send an implementation request and verify the CTO → Implementer → Reviewer → CTO workflow executes correctly.

## Rollback

If you need to undo DS-EO installation:

```bash
# Restore from backup
LATEST_BACKUP=$(ls -t ~/.openclaw/backups/ds-eo-openclaw-*.json.bak | head -1)
cp "$LATEST_BACKUP" ~/.openclaw/openclaw.json

# Remove protocol files (optional)
bash scripts/deploy_protocols.sh --rollback
```

## FAQ

**Q: Will this break my existing DS-AIOS development?**  
A: No. DS-EO only extracts the engineering organization layer. Your runtime agents and application code are untouched.

**Q: What happens to my current protocol files at `~/.openclaw/protocols/`?**  
A: They're backed up with `.ds-eo-bak` suffix before being overwritten by DS-EO's authoritative copies. You can restore them anytime.

**Q: Can I use different models than the defaults?**  
A: Yes! During installation, you specify model names for each role. The defaults are suggestions based on what's currently in use.

**Q: Do I need to modify AGENTS.md?**  
A: DS-EO deployment copies protocol and prompt files to your project workspace. You may want to update `AGENTS.md` references from `docs/development/protocols/` to the new locations, but this is optional — DS-EO protocols work regardless of reference paths.
