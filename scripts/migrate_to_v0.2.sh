#!/usr/bin/env bash
# migrate_to_v0.2.sh — Upgrade DS-EO from v0.1.x to v0.2.x
#
# Usage:
#   migrate_to_v0.2.sh [--dry-run] [--force] [--target-version <version>]
#
# What it does:
#   1. Detects current installed version (from manifest or config)
#   2. Validates compatibility with target version
#   3. Lists all changes needed (config fields, protocol updates, template format changes)
#   4. Dry-run mode shows exact diff without applying
#   5. Confirm mode applies changes with backup before each modification
#
# Exit codes:
#   0 — Migration successful or dry-run completed
#   1 — Incompatible version or migration failed
#   2 — Invalid usage

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENCLAW_DIR="${DS_EO_OPENCLAW_DIR:-$HOME/.openclaw}"
CONFIG_FILE="$OPENCLAW_DIR/openclaw.json"

DRY_RUN=false
FORCE=false
TARGET_VERSION="0.2.0"

# ─── Argument Parsing ──────────────────────────────────────────────

for arg in "$@"; do
    case "$arg" in
        --dry-run)          DRY_RUN=true ;;
        --force)            FORCE=true ;;
        --target-version=*) TARGET_VERSION="${arg#*=}" ;;
        *)                  echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

# ─── Helpers ──────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()    { echo -e "${CYAN}[Migrate]${NC} $*"; }
ok()     { echo -e "  ${GREEN}✓${NC} $*"; }
warn()   { echo -e "  ${YELLOW}⚠${NC} $*"; }
err()    { echo -e "  ${RED}✗${NC} $*"; }
info()   { echo -e "${BOLD}$*${NC}"; }

# ─── Step 1: Detect Current Version ──────────────────────────────

info "--- Step 1/5: Detecting current version ---"

CURRENT_VERSION=""

# Check manifest file first
if [[ -f "$PKG_ROOT/ds_eo_manifest.yaml" ]]; then
    CURRENT_VERSION=$(grep 'version:' "$PKG_ROOT/ds_eo_manifest.yaml" | head -1 | awk '{print $2}' | tr -d '"' | tr -d "'")
fi

# Fallback: check openclaw.json for version metadata
if [[ -z "$CURRENT_VERSION" ]] && [[ -f "$CONFIG_FILE" ]]; then
    CURRENT_VERSION=$(python3 -c "
import json, sys
try:
    with open('$CONFIG_FILE') as f:
        data = json.load(f)
    # Check agents.defaults for version field (if any)
    defaults = data.get('agents', {}).get('defaults', {})
    print(defaults.get('version', ''))
except Exception as e:
    sys.exit(1)
" 2>/dev/null) || true
fi

# Fallback: check package.json or other version files
if [[ -z "$CURRENT_VERSION" ]]; then
    for ver_file in "$PKG_ROOT/package.json" "$PKG_ROOT/VERSION" "$PKG_ROOT/.version"; do
        if [[ -f "$ver_file" ]]; then
            CURRENT_VERSION=$(grep -oE '[0-9]+\.[0-9]+\.[0-9]+' "$ver_file" | head -1)
            break
        fi
    done
fi

if [[ -z "$CURRENT_VERSION" ]]; then
    err "Cannot detect current DS-EO version."
    echo ""
    echo "  This migration script is designed for upgrading from v0.1.x to v0.2.x."
    echo "  If you're already on v0.2+, no migration is needed."
    exit 1
fi

log "Current version: $CURRENT_VERSION"
info "Target version:  $TARGET_VERSION"
echo ""

# ─── Step 2: Validate Compatibility ──────────────────────────────

info "--- Step 2/5: Validating compatibility ---"

# Check if already on target or newer
if [[ "$CURRENT_VERSION" == "$TARGET_VERSION"* ]]; then
    ok "Already on v0.2.x — no migration needed."
    exit 0
fi

# Check if upgrading from compatible range (v0.1.x)
if [[ "$CURRENT_VERSION" =~ ^0\.1\.[0-9]+$ ]]; then
    ok "Compatible upgrade path: $CURRENT_VERSION → $TARGET_VERSION"
else
    err "Incompatible version: $CURRENT_VERSION"
    echo ""
    echo "  This migration supports upgrades from v0.1.x to v0.2.x."
    echo "  For other versions, consult the upgrade documentation or perform manual migration."
    exit 1
fi

# ─── Step 3: Identify Required Changes ──────────────────────────

info "--- Step 3/5: Identifying required changes ---"

declare -a CHANGES=()
declare -A CHANGE_DESCRIPTIONS=(
    ["config_update"]="Update openclaw.json with new agent fields and defaults"
    ["protocol_migration"]="Migrate protocol files to v0.2 format (if breaking changes)"
    ["template_update"]="Update template formats if structure changed"
    ["manifest_update"]="Update ds_eo_manifest.yaml version"
)

# Check for config field changes needed
CONFIG_CHANGES_NEEDED=false
if [[ -f "$CONFIG_FILE" ]]; then
    # Check if current config has the new v0.2 fields
    HAS_NEW_FIELDS=$(python3 -c "
import json, sys
try:
    with open('$CONFIG_FILE') as f:
        data = json.load(f)
    agents = data.get('agents', {}).get('list', [])
    # Check if any agent has 'profile' field (new in v0.2)
    has_profile = any('profile' in a for a in agents if isinstance(a, dict))
    print('yes' if has_profile else 'no')
except Exception as e:
    sys.exit(1)
" 2>/dev/null) || HAS_NEW_FIELDS="unknown"

    if [[ "$HAS_NEW_FIELDS" == "no" ]]; then
        CONFIG_CHANGES_NEEDED=true
        CHANGES+=("config_update")
    fi
fi

# Check for protocol format changes (if any breaking changes in v0.2 protocols)
PROTOCOLS_DIR="$OPENCLAW_DIR/protocols/"
if [[ -d "$PROTOCOLS_DIR" ]]; then
    # For now, assume no protocol format changes unless explicitly documented
    # This would be extended if v0.2 actually breaks protocol formats
    :
fi

# Check for manifest version mismatch
if [[ -f "$PKG_ROOT/ds_eo_manifest.yaml" ]]; then
    MANIFEST_VERSION=$(grep 'version:' "$PKG_ROOT/ds_eo_manifest.yaml" | head -1 | awk '{print $2}' | tr -d '"' | tr -d "'")
    if [[ "$MANIFEST_VERSION" != "$TARGET_VERSION"* ]]; then
        CHANGES+=("manifest_update")
    fi
fi

if [[ ${#CHANGES[@]} -eq 0 ]]; then
    ok "No changes required — already compatible."
else
    info "Changes identified:"
    for change in "${CHANGES[@]}"; do
        echo "  • ${CHANGE_DESCRIPTIONS[$change]}"
    done
fi
echo ""

# ─── Step 4: Dry Run or Apply Changes ────────────────────────────

if [[ "$DRY_RUN" == true ]]; then
    info "--- Step 4/5 (dry-run): Showing changes ---"
    echo ""

    for change in "${CHANGES[@]}"; do
        case "$change" in
            config_update)
                if [[ -f "$CONFIG_FILE" ]]; then
                    log "[dry-run] Would update openclaw.json with v0.2 agent fields:"
                    echo "  • Add 'profile' field to implementer agent (coding profile)"
                    echo "  • Update defaults.model.primary if needed"
                    echo "  • Backup: ${CONFIG_FILE}.bak.pre-migrate-v0.2"
                fi
                ;;
            manifest_update)
                log "[dry-run] Would update ds_eo_manifest.yaml:"
                echo "  • version: $MANIFEST_VERSION → $TARGET_VERSION"
                ;;
        esac
    done

    echo ""
    info "=== Dry Run Complete ==="
    echo "  No changes were made. Run without --dry-run to apply."
    exit 0
else
    info "--- Step 4/5: Applying changes ---"
    echo ""

    for change in "${CHANGES[@]}"; do
        case "$change" in
            config_update)
                if [[ -f "$CONFIG_FILE" ]]; then
                    # Backup before modification
                    BACKUP_FILE="${CONFIG_FILE}.bak.pre-migrate-v0.2"
                    cp "$CONFIG_FILE" "$BACKUP_FILE"
                    ok "Backup created: $BACKUP_FILE"

                    # Apply v0.2 changes (add profile field to implementer)
                    python3 -c "
import json, sys

config_path = '$CONFIG_FILE'
with open(config_path, 'r') as f:
    config = json.load(f)

agents_list = config.get('agents', {}).get('list', [])

# Add profile field to implementer if missing
for agent in agents_list:
    if isinstance(agent, dict) and agent.get('id') == 'implementer':
        if 'profile' not in agent:
            agent['profile'] = 'coding'
            print(f\"Updated implementer agent with profile='coding'\")

# Update defaults.model.primary if it points to old default model
defaults = config.get('agents', {}).get('defaults', {})
model_defaults = defaults.setdefault('model', {})
if model_defaults.get('primary') == 'ollama/qwen3.6:35b':
    # Keep as-is unless v0.2 specifies a different primary
    pass

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
print(f\"Config updated: {config_path}\")
" 2>&1 || err "Failed to update config"
                fi
                ;;
            manifest_update)
                if [[ -f "$PKG_ROOT/ds_eo_manifest.yaml" ]]; then
                    # Backup first
                    cp "$PKG_ROOT/ds_eo_manifest.yaml" "${PKG_ROOT}/ds_eo_manifest.yaml.bak.pre-migrate-v0.2"

                    # Update version in YAML (simple sed for this field)
                    sed -i "s/^  version: .*/  version: \"$TARGET_VERSION\"/" "$PKG_ROOT/ds_eo_manifest.yaml"
                    ok "Updated ds_eo_manifest.yaml to v$TARGET_VERSION"
                fi
                ;;
        esac
    done

    echo ""
fi

# ─── Step 5: Verify Migration ─────────────────────────────────────

info "--- Step 5/5: Verifying migration ---"

if [[ "$DRY_RUN" == false ]]; then
    # Re-detect version to confirm update
    NEW_VERSION=""
    if [[ -f "$PKG_ROOT/ds_eo_manifest.yaml" ]]; then
        NEW_VERSION=$(grep 'version:' "$PKG_ROOT/ds_eo_manifest.yaml" | head -1 | awk '{print $2}' | tr -d '"' | tr -d "'")
    fi

    if [[ -n "$NEW_VERSION" && "$NEW_VERSION" == "$TARGET_VERSION"* ]]; then
        ok "Migration successful: $CURRENT_VERSION → $NEW_VERSION"
    else
        warn "Version not updated as expected. Check ds_eo_manifest.yaml manually."
    fi

    # Verify backup exists
    if [[ -f "${CONFIG_FILE}.bak.pre-migrate-v0.2" ]]; then
        ok "Backup preserved: ${CONFIG_FILE}.bak.pre-migrate-v0.2"
    else
        warn "No backup found — this is unusual, check migration logs."
    fi

    echo ""
fi

# ─── Summary ──────────────────────────────────────────────────────

echo ""
if [[ "$DRY_RUN" == true ]]; then
    info "=== Migration Dry Run Complete ==="
else
    info "=== Migration Complete ==="
    echo ""
    echo "  Next steps:"
    echo "    1. Review changes in ${CONFIG_FILE}.bak.pre-migrate-v0.2 if needed"
    echo "    2. Restart OpenClaw: openclaw gateway restart"
    echo "    3. Verify agents work correctly"
    echo ""
    echo "  Rollback (if needed):"
    echo "    cp ${CONFIG_FILE}.bak.pre-migrate-v0.2 $CONFIG_FILE"
fi
