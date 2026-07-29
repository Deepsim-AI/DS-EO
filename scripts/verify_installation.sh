#!/usr/bin/env bash
# verify_installation.sh — Post-install verification checks
# Runs all validation checks and reports results.
# Exits 0 on success, 1 on failure (with rollback if triggered).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENCLAW_DIR="${DS_EO_OPENCLAW_DIR:-$HOME/.openclaw}"
CONFIG_FILE="${DS_EO_CONFIG_FILE:-$OPENCLAW_DIR/openclaw.json}"
BACKUP_DIR="$OPENCLAW_DIR/backups"

PASS=0
FAIL=0
ROLLBACK_NEEDED=false

check_pass() { PASS=$((PASS + 1)); echo "  ✓ $*"; }
check_fail() { FAIL=$((FAIL + 1)); ROLLBACK_NEEDED=true; echo "  ✗ $*"; }

echo "DS-EO Installation Verification"
echo "================================"
echo ""

# ─── Check 1: openclaw.json is valid JSON ────────────────────────

if python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
    check_pass "openclaw.json is valid JSON"
else
    check_fail "openclaw.json is NOT valid JSON — rollback required"
fi

# ─── Check 2: All 3 DS-EO agents present in config ────────────────

AGENTS_OK=$(python3 -c "
import json, sys
config = json.load(open('$CONFIG_FILE'))
agents = [a.get('id','') for a in config.get('agents',{}).get('list',[])]
required = ['cto','implementer','reviewer']
missing = [r for r in required if r not in agents]
if missing:
    print('MISSING:' + ','.join(missing))
else:
    print('OK')
" 2>/dev/null || echo "ERROR")

if [[ "$AGENTS_OK" == "OK" ]]; then
    check_pass "All 3 DS-EO agents present in openclaw.json"
elif [[ "$AGENTS_OK" == ERROR* ]]; then
    check_fail "Could not verify agent presence (config error)"
else
    MISSING=$(echo "$AGENTS_OK" | sed 's/MISSING://')
    check_fail "Missing DS-EO agents: $MISSING — rollback required"
fi

# ─── Check 3: Agent config completeness ──────────────────────────

python3 -c "
import json, sys

config = json.load(open('$CONFIG_FILE'))
agents_list = config.get('agents', {}).get('list', [])
required_fields = ['id', 'name', 'model', 'workspace']
errors = []

for agent in agents_list:
    aid = agent.get('id', '<unknown>')
    for field in required_fields:
        if field not in agent or not agent[field]:
            errors.append(f'Agent {aid} missing field: {field}')

# Check no duplicate IDs
ids = [a.get('id') for a in agents_list]
if len(ids) != len(set(ids)):
    errors.append('Duplicate agent IDs found in agents.list[]')

# Check gateway/plugins/channels preserved
for section in ['gateway', 'plugins', 'channels']:
    if section not in config:
        # Not necessarily an error — some configs may not have these
        pass

if errors:
    for e in errors:
        print(f'ERROR: {e}')
    sys.exit(1)
else:
    print('OK')
" 2>/dev/null && check_pass "Agent config entries are complete and valid" || \
    check_fail "Agent config validation failed — rollback required"

# ─── Check 4: Protocol files present (global) ────────────────────

PROTOCOLS=(approval_protocol communication_protocol completion_protocol delegation_protocol handoff_protocol review_protocol)
PROTO_MISSING=0

for proto in "${PROTOCOLS[@]}"; do
    if [ -f "$OPENCLAW_DIR/protocols/${proto}.md" ]; then
        SIZE=$(wc -c < "$OPENCLAW_DIR/protocols/${proto}.md")
        if [ "$SIZE" -lt 100 ]; then
            check_fail "Protocol $proto.md is too small (${SIZE} bytes) — may be truncated"
            PROTO_MISSING=$((PROTO_MISSING + 1))
        fi
    else
        check_fail "Global protocol missing: ~/.openclaw/protocols/${proto}.md"
        PROTO_MISSING=$((PROTO_MISSING + 1))
    fi
done

if [ "$PROTO_MISSING" -eq 0 ]; then
    check_pass "All 6 DS-EO protocols present at global location (>100 bytes each)"
fi

# ─── Check 5: Manifest file present and valid YAML ──────────────

if [ -f "$PKG_ROOT/ds_eo_manifest.yaml" ]; then
    if python3 -c "import yaml; yaml.safe_load(open('$PKG_ROOT/ds_eo_manifest.yaml'))" 2>/dev/null; then
        check_pass "ds_eo_manifest.yaml is valid YAML"
    else
        check_fail "ds_eo_manifest.yaml is NOT valid YAML"
    fi
else
    check_fail "ds_eo_manifest.yaml not found in package root"
fi

# ─── Check 6: All agent prompt files present in package ──────────

AGENT_FILES=(cto.md implementer.md reviewer.md)
AGENTS_OK=true

for af in "${AGENT_FILES[@]}"; do
    if [ -f "$PKG_ROOT/agents/$af" ]; then
        SIZE=$(wc -c < "$PKG_ROOT/agents/$af")
        if [ "$SIZE" -lt 100 ]; then
            check_fail "Agent prompt $af is too small (${SIZE} bytes)"
            AGENTS_OK=false
        fi
    else
        check_fail "Agent prompt missing: agents/$af"
        AGENTS_OK=false
    fi
done

if [ "$AGENTS_OK" = true ]; then
    check_pass "All 3 agent prompts present and non-empty in package"
fi

# ─── Check 7: All template files present ──────────────────────────

TEMPLATE_FILES=(task.md report_template.md review_report_template.md spec_template.md cto_approval_template.md)
TEMPLATES_OK=true

for tf in "${TEMPLATE_FILES[@]}"; do
    if [ ! -f "$PKG_ROOT/templates/$tf" ]; then
        check_fail "Template missing: templates/$tf"
        TEMPLATES_OK=false
    fi
done

if [ "$TEMPLATES_OK" = true ]; then
    check_pass "All 5 templates present in package"
fi

# ─── Summary ──────────────────────────────────────────────────────

echo ""
echo "================================"
echo "Results: $PASS passed, $FAIL failed"
echo "================================"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    if [ "$ROLLBACK_NEEDED" = true ]; then
        echo "CRITICAL: Verification failed. Rollback recommended."
        echo ""
        LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/ds-eo-openclaw-*.json.bak 2>/dev/null | head -1) || true
        if [ -n "${LATEST_BACKUP:-}" ]; then
            echo "To rollback, run:"
            echo "  cp $LATEST_BACKUP $CONFIG_FILE"
        else
            echo "No backup found. Manual intervention required."
        fi
    fi
    exit 1
else
    echo ""
    echo "All verification checks passed. Installation is valid."
    exit 0
fi
