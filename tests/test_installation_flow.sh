#!/usr/bin/env bash
# test_installation_flow.sh — End-to-end installation smoke test (on clean host)
# Tests the full install → verify → rollback flow on a temporary environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_TMPDIR=$(mktemp -d /tmp/ds-eo-smoke-test-XXXXXX)

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  ✓ $*"; }
fail() { FAIL=$((FAIL + 1)); echo "  ✗ $*"; }

cleanup() { rm -rf "$TEST_TMPDIR"; }
trap cleanup EXIT

echo "DS-EO Installation Flow Smoke Test"
echo "==================================="
echo ""

# ─── Setup: Create clean test environment ──────────────────────

echo "--- Setup ---"
export TEST_OPENCLAW_DIR="$TEST_TMPDIR/openclaw-home"
export TEST_CONFIG_FILE="$TEST_OPENCLAW_DIR/openclaw.json"
mkdir -p "$TEST_OPENCLAW_DIR/protocols"

# Create a minimal openclaw.json with no DS-EO agents
cat > "$TEST_CONFIG_FILE" <<'EOF'
{
  "gateway": {"port": 3000},
  "plugins": {"entries": []},
  "agents": {
    "defaults": {"model": {"primary": ""}},
    "list": [
      {"id": "other-agent", "name": "Other Agent", "model": "ollama/qwen3-coder:latest", "workspace": "/home/deepsim/test-project"}
    ]
  }
}
EOF

# Set env vars so scripts use test directories instead of real ones
export DS_EO_OPENCLAW_DIR="$TEST_OPENCLAW_DIR"
pass "Clean test environment created"

# ─── Step 1: Backup ──────────────────────────────────────────

echo ""
echo "--- Step 1: Backup ---"
bash "$PKG_ROOT/scripts/backup_openclaw_config.sh" --target "$TEST_CONFIG_FILE" 2>/dev/null
BACKUP_DIR="$TEST_OPENCLAW_DIR/backups"
if ls "$BACKUP_DIR"/ds-eo-openclaw-*.json.bak &>/dev/null; then
    pass "Backup created successfully"
else
    fail "Backup not created (checked $BACKUP_DIR)"
fi

# ─── Step 2: Generate Config (non-interactive) ────────────────

echo ""
echo "--- Step 2: Generate Config ---"
export CTO_MODEL="ollama/qwen3.6:35b"
export IMPL_MODEL="ollama/ornith:35b"
export REV_MODEL="ollama/laguna-xs-2.1:q4_K_M"

# Simulate interactive input with defaults (empty = use default model names)
printf '\n\n\n' | DS_EO_OPENCLAW_DIR="$TEST_OPENCLAW_DIR" bash "$PKG_ROOT/scripts/generate_openclaw_config.sh" --generate 2>/dev/null || true

if [ -f "$PKG_ROOT/agents_list.json" ]; then
    pass "Agent config generated (agents_list.json)"
else
    fail "Agent config generation failed"
fi

# ─── Step 3: Merge Config ─────────────────────────────────────

echo ""
echo "--- Step 3: Merge Config ---"
# Merge using the test config file (env var override)
DS_EO_OPENCLAW_DIR="$TEST_OPENCLAW_DIR" bash "$PKG_ROOT/scripts/generate_openclaw_config.sh" --merge "$PKG_ROOT/agents_list.json" 2>/dev/null || true

if python3 -c "import json; json.load(open('$TEST_CONFIG_FILE'))" 2>/dev/null; then
    pass "Merged config is valid JSON"
else
    fail "Merged config is NOT valid JSON"
fi

# Verify DS-EO agents present
AGENTS=$(python3 -c "
import json
config = json.load(open('$TEST_CONFIG_FILE'))
ids = [a['id'] for a in config.get('agents',{}).get('list',[])]
print(','.join(sorted(ids)))
" 2>/dev/null)

if echo "$AGENTS" | grep -q "cto" && echo "$AGENTS" | grep -q "implementer" && echo "$AGENTS" | grep -q "reviewer"; then
    pass "All DS-EO agents present: $AGENTS"
else
    fail "Missing DS-EO agents in merged config: $AGENTS"
fi

# Verify existing agent preserved
if python3 -c "
import json
config = json.load(open('$TEST_CONFIG_FILE'))
ids = [a['id'] for a in config.get('agents',{}).get('list',[])]
exit(0 if 'other-agent' in ids else 1)
" 2>/dev/null; then
    pass "Existing non-DS-EO agent preserved"
else
    fail "Existing agent was removed during merge"
fi

# ─── Step 4: Deploy Protocols (Global) ────────────────────────

echo ""
echo "--- Step 4: Deploy Protocols ---"
bash "$PKG_ROOT/scripts/deploy_protocols.sh" --target "$TEST_OPENCLAW_DIR/protocols/" 2>/dev/null || true

PROTO_COUNT=$(ls "$TEST_OPENCLAW_DIR/protocols/"*.md 2>/dev/null | wc -l)
if [ "$PROTO_COUNT" -ge 6 ]; then
    pass "All protocols deployed ($PROTO_COUNT files)"
else
    fail "Only $PROTO_COUNT protocol files deployed (expected ≥6)"
fi

# ─── Step 5: Verify Installation ──────────────────────────────

echo ""
echo "--- Step 5: Verification ---"

# Run verification against test environment
export CONFIG_FILE="$TEST_CONFIG_FILE"
if bash "$PKG_ROOT/scripts/verify_installation.sh" 2>/dev/null; then
    pass "Verification passed on test environment"
else
    fail "Verification failed on test environment"
fi

# ─── Step 6: Test Rollback ────────────────────────────────────

echo ""
echo "--- Step 6: Rollback ---"

# Corrupt the config to trigger rollback need
cat > "$TEST_CONFIG_FILE" <<'EOF'
{this is not valid json!!!
EOF

if python3 -c "import json; json.load(open('$TEST_CONFIG_FILE'))" 2>/dev/null; then
    fail "Config corruption test failed — file should be invalid JSON"
else
    pass "Config successfully corrupted for rollback test"
fi

# Restore from backup
# Restore from backup in test directory
LATEST_BACKUP=$(ls -t "$TEST_OPENCLAW_DIR/backups/ds-eo-openclaw-"*.json.bak 2>/dev/null | head -1) || true
if [ -n "$LATEST_BACKUP" ]; then
    cp "$LATEST_BACKUP" "$TEST_CONFIG_FILE"
    if python3 -c "import json; json.load(open('$TEST_CONFIG_FILE'))"; then
        pass "Rollback restored valid config from backup"
    else
        fail "Rollback did not restore valid JSON"
    fi
else
    fail "No backup found for rollback test"
fi

# ─── Summary ──────────────────────────────────────────────────

echo ""
echo "==================================="
echo "Results: $PASS passed, $FAIL failed"
echo "==================================="

if [ "$FAIL" -gt 0 ]; then
    echo ""
    echo "Smoke test FAILED. Check output above for details."
    exit 1
else
    echo ""
    echo "All smoke tests passed!"
    exit 0
fi
