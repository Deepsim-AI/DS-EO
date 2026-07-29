#!/usr/bin/env bash
# install.sh — DS-EO OpenClaw Edition Main Installer (Orchestrator)
# Runs all installation steps in order with verification between each.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENCLAW_DIR="$HOME/.openclaw"
CONFIG_FILE="$OPENCLAW_DIR/openclaw.json"
BACKUP_DIR="$OPENCLAW_DIR/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()    { echo -e "${CYAN}[DS-EO]${NC} $*"; }
ok()     { echo -e "  ${GREEN}✓${NC} $*"; }
warn()   { echo -e "  ${YELLOW}⚠${NC} $*"; }
err()    { echo -e "  ${RED}✗${NC} $*"; }

# ─── Pre-flight Checks ──────────────────────────────────────────────

log "DS-EO OpenClaw Edition — Installation"
echo ""

# Check openclaw.json exists and is valid JSON
if [ ! -f "$CONFIG_FILE" ]; then
    err "openclaw.json not found at $CONFIG_FILE"
    echo "  Please ensure OpenClaw is installed and configured."
    exit 1
fi

if ! python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
    err "openclaw.json is not valid JSON — aborting for safety"
    echo "  Backup your file first, then investigate the corruption."
    exit 1
fi
ok "openclaw.json exists and is valid JSON"

# Check disk space (>50MB free)
FREE_KB=$(df -k "$OPENCLAW_DIR" | tail -1 | awk '{print $4}')
if [ "$FREE_KB" -lt 50000 ]; then
    warn "Low disk space: ${FREE_KB}KB available (need >50MB)"
    read -r -p "Continue anyway? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || exit 1
else
    ok "Sufficient disk space (${FREE_KB}KB free)"
fi

# Check for existing DS-EO installation
if python3 -c "
import json
config = json.load(open('$CONFIG_FILE'))
agents = [a.get('id','') for a in config.get('agents',{}).get('list',[])]
raise SystemExit(0 if any(a in agents for a in ['cto','implementer','reviewer']) else 1)
" 2>/dev/null; then
    warn "DS-EO agents already found in openclaw.json"
    read -r -p "Reinstall (will overwrite existing DS-EO entries)? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || exit 0
else
    ok "Clean install — no existing DS-EO agents detected"
fi

echo ""

# ─── Step 1: Backup ────────────────────────────────────────────────

log "Step 1/7: Backing up openclaw.json..."
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%dT%H%M%S)
cp "$CONFIG_FILE" "$BACKUP_DIR/ds-eo-openclaw-${TIMESTAMP}.json.bak"
ok "Backup created: $BACKUP_DIR/ds-eo-openclaw-${TIMESTAMP}.json.bak"

# ─── Step 2: Generate Agent Config (Interactive) ──────────────────

log ""
log "Step 2/7: Generating agent configuration..."
echo ""
bash "$SCRIPT_DIR/generate_openclaw_config.sh" --generate
if [ ! -f "$PKG_ROOT/agents_list.json" ]; then
    err "Config generation failed — agents_list.json not created"
    exit 1
fi
ok "Agent config generated: $PKG_ROOT/agents_list.json"

# ─── Step 3: Merge into openclaw.json ──────────────────────────────

log ""
log "Step 3/7: Merging agent configuration..."
bash "$SCRIPT_DIR/generate_openclaw_config.sh" --merge "$PKG_ROOT/agents_list.json"

if ! python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
    err "Merge produced invalid JSON — rolling back"
    bash "$SCRIPT_DIR/install.sh" --rollback-only 2>/dev/null || true
    exit 1
fi
ok "Config merged and validated successfully"

# ─── Step 4: Deploy Protocols (Global) ─────────────────────────────

log ""
log "Step 4/7: Deploying protocols (global)..."
bash "$SCRIPT_DIR/deploy_protocols.sh" --target "$OPENCLAW_DIR/protocols/"
ok "Protocols deployed to $OPENCLAW_DIR/protocols/"

# ─── Step 5: Deploy Protocols (Per-Project, Optional) ──────────────

log ""
log "Step 5/7: Per-project protocol deployment"

# Default to the current working directory's project path if it has docs/development/
PROJECT_PROTOCOLS=""
if [ -d "${PWD}/docs/development/protocols/" ]; then
    PROJECT_PROTOCOLS="${PWD}/docs/development/protocols/"
fi

if [ -n "$PROJECT_PROTOCOLS" ]; then
    read -r -p "Deploy protocols to $PROJECT_PROTOCOLS? [Y/n] " confirm
    if [[ ! "$confirm" =~ ^[Nn]$ ]]; then
        bash "$SCRIPT_DIR/deploy_protocols.sh" --target "$PROJECT_PROTOCOLS"
        ok "Protocols deployed to project workspace"
    else
        warn "Skipping per-project protocol deployment"
    fi
else
    # Check if user has any project with docs/development/protocols/
    echo ""
    read -r -p "Deploy protocols to a project workspace? (y/N) " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        read -r -p "Project path: " proj_path
        if [ -n "$proj_path" ]; then
            bash "$SCRIPT_DIR/deploy_protocols.sh" --target "${proj_path}/docs/development/protocols/"
            ok "Protocols deployed to $proj_path/docs/development/protocols/"
        fi
    else
        warn "Skipping per-project protocol deployment (optional)"
    fi
fi

# ─── Step 6: Deploy Agent Prompts (Per-Project) ────────────────────

log ""
log "Step 6/7: Deploying agent prompts..."

if [ -d "${PWD}/docs/prompts/" ]; then
    bash "$SCRIPT_DIR/deploy_agents.sh" --target "${PWD}/docs/prompts/"
    ok "Agent prompts deployed to $PWD/docs/prompts/"
else
    echo ""
    read -r -p "Deploy agent prompts to a project? (y/N) " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        read -r -p "Project path: " proj_path
        if [ -n "$proj_path" ]; then
            bash "$SCRIPT_DIR/deploy_agents.sh" --target "${proj_path}/docs/prompts/"
            ok "Agent prompts deployed to $proj_path/docs/prompts/"
        fi
    else
        warn "Skipping per-project prompt deployment (optional)"
    fi
fi

# ─── Step 7: Verify Installation ──────────────────────────────────

log ""
log "Step 7/7: Verifying installation..."
echo ""

if bash "$SCRIPT_DIR/verify_installation.sh"; then
    echo ""
    log "${GREEN}Installation complete!${NC}"
    echo ""
    echo "  Next steps:"
    echo "    1. Restart OpenClaw to load new agent configurations"
    echo "    2. Verify agents appear in your session list"
    echo "    3. Send an implementation request to start a task cycle"
    echo ""
    log "Backup location: $BACKUP_DIR/"
else
    err "Verification failed — initiating automatic rollback..."
    bash "$SCRIPT_DIR/install.sh" --rollback-only || true
    exit 1
fi
