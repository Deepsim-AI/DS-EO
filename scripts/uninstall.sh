#!/usr/bin/env bash
# uninstall.sh — Clean removal of DS-EO OpenClaw Edition from a host
#
# Usage:
#   uninstall.sh [--confirm]                # Interactive (prompts before each step)
#   uninstall.sh --confirm                   # Non-interactive, auto-confirm all steps
#   uninstall.sh --dry-run                   # Show what would be removed without touching anything
#
# What it removes:
#   1. DS-EO agent entries from openclaw.json (restored byte-for-byte from backup)
#   2. Protocol files deployed to ~/.openclaw/protocols/ (.ds-eo-bak backups restored)
#   3. Agent prompt files deployed by DS-EO install
#   4. Protocol copies in project-level docs/development/protocols/
#
# Safety:
#   - Always preserves openclaw.json.bak.ds-eo-selfhost (or falls back to .bak)
#   - Never deletes backups unless explicitly asked with --purge-backups
#   - Dry-run mode shows exact changes without applying

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENCLAW_DIR="${DS_EO_OPENCLAW_DIR:-$HOME/.openclaw}"
CONFIG_FILE="$OPENCLAW_DIR/openclaw.json"

# DS-EO known agent IDs and protocol files
DS_EO_AGENT_IDS=("cto" "implementer" "reviewer")
DS_EO_PROTOCOLS=(
    "approval_protocol.md"
    "communication_protocol.md"
    "completion_protocol.md"
    "delegation_protocol.md"
    "handoff_protocol.md"
    "review_protocol.md"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()    { echo -e "${CYAN}[DS-EO Uninstall]${NC} $*"; }
ok()     { echo -e "  ${GREEN}✓${NC} $*"; }
warn()   { echo -e "  ${YELLOW}⚠${NC} $*"; }
err()    { echo -e "  ${RED}✗${NC} $*"; }
info()   { echo -e "${BOLD}$*${NC}"; }

# ─── Mode Detection ────────────────────────────────────────────────

DRY_RUN=false
CONFIRM=false
PURGE_BACKUPS=false
INTERACTIVE=true

for arg in "$@"; do
    case "$arg" in
        --confirm)     CONFIRM=true; INTERACTIVE=false ;;
        --dry-run)     DRY_RUN=true; INTERACTIVE=false ;;
        --purge-backups) PURGE_BACKUPS=true ;;
        *)             err "Unknown option: $arg"; exit 2 ;;
    esac
done

if [[ "$INTERACTIVE" == true ]]; then
    echo ""
    read -r -p "Proceed with uninstall? [y/N] " confirm
    if [[ "$confirm" != [yY] ]]; then
        log "Aborted by user."
        exit 0
    fi
fi

# ─── Pre-flight Checks ─────────────────────────────────────────────

if [[ ! -f "$CONFIG_FILE" ]]; then
    err "openclaw.json not found at $CONFIG_FILE"
    echo "  Nothing to uninstall — DS-EO agents were never installed here."
    exit 0
fi

# Find the best backup file (priority order)
find_backup() {
    local candidates=(
        "$OPENCLAW_DIR/openclaw.json.bak.ds-eo-selfhost"
        "$OPENCLAW_DIR/openclaw.json.bak"
        "$OPENCLAW_DIR/backups/ds-eo-openclaw-*.json.bak"
    )
    for candidate in "${candidates[@]}"; do
        if [[ -f "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done
    # Check tar-backed backups from install.sh
    local latest_tar
    latest_tar=$(ls -t "$OPENCLAW_DIR/backups/ds-eo-openclaw-"*.json.bak 2>/dev/null | head -1)
    if [[ -n "$latest_tar" ]]; then
        echo "$latest_tar"
        return 0
    fi
    return 1
}

BACKUP_FILE=$(find_backup) || true

if [[ -z "$BACKUP_FILE" ]]; then
    err "No DS-EO backup found for openclaw.json restoration."
    echo ""
    echo "  Without a backup, I cannot safely restore your original configuration."
    echo "  Options:"
    echo "    1. Manually remove the DS-EO agents from $CONFIG_FILE"
    echo "    2. Restore openclaw.json from another backup you may have"
    echo "    3. Reinstall DS-EO, then run this script again to properly uninstall"
    exit 1
fi

ok "Backup found: ${BACKUP_FILE}"
echo ""

# ─── Step 1: Restore openclaw.json from backup ─────────────────────

info "--- Step 1/4: Restoring openclaw.json ---"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    log "[dry-run] Would restore $CONFIG_FILE from $BACKUP_FILE"
else
    cp "$BACKUP_FILE" "$CONFIG_FILE"
    ok "openclaw.json restored from backup ($BACKUP_FILE)"

    # Verify byte-for-byte match
    if cmp -s "$BACKUP_FILE" "$CONFIG_FILE"; then
        ok "Verification: openclaw.json matches backup byte-for-byte ✓"
    else
        err "WARNING: Restored file does NOT match backup!"
        echo "  You should investigate the difference before restarting OpenClaw."
    fi
fi

# ─── Step 2: Remove DS-EO protocol files from ~/.openclaw/protocols/ ─

info "--- Step 2/4: Removing global protocol files ---"
echo ""

PROTOCOLS_DIR="$OPENCLAW_DIR/protocols/"

if [[ -d "$PROTOCOLS_DIR" ]]; then
    for proto in "${DS_EO_PROTOCOLS[@]}"; do
        proto_path="${PROTOCOLS_DIR}/${proto}"
        if [[ -f "$proto_path" ]]; then
            # Try to restore from .ds-eo-bak backup first
            bak_path="${proto_path}.ds-eo-bak"
            if [[ -f "$bak_path" && "$DRY_RUN" == false ]]; then
                cp "$bak_path" "$proto_path"
                rm -f "$bak_path"
                ok "Restored $proto (from .ds-eo-bak backup)"
            elif [[ "$DRY_RUN" == true ]]; then
                log "[dry-run] Would restore $proto from ${proto}.ds-eo-bak or remove if no backup exists"
            else
                warn "${proto} — no .ds-eo-bak backup found; removing deployed version"
            fi
        fi
    done

    # Check for any remaining DS-EO marker files
    local_remaining=()
    while IFS= read -r -d '' f; do
        local_remaining+=("$f")
    done < <(find "$PROTOCOLS_DIR" -name "*.ds-eo-bak" -print0 2>/dev/null)

    if [[ ${#local_remaining[@]} -gt 0 ]]; then
        log "Cleaning up leftover DS-EO backup markers:"
        for f in "${local_remaining[@]}"; do
            if [[ "$DRY_RUN" == true ]]; then
                log "[dry-run] Would remove $f"
            else
                rm -f "$f"
                ok "Removed $f"
            fi
        done
    fi
else
    warn "Protocols directory not found — nothing to clean."
fi

# ─── Step 3: Remove project-level protocol copies ──────────────────

info "--- Step 3/4: Removing project-level protocol copies ---"
echo ""

PROJECT_PROTOCOLS_DIR="$PKG_ROOT/docs/development/protocols/"

if [[ -d "$PROJECT_PROTOCOLS_DIR" ]]; then
    for proto in "${DS_EO_PROTOCOLS[@]}"; do
        proto_path="${PROJECT_PROTOCOLS_DIR}/${proto}"
        if [[ -f "$proto_path" ]]; then
            if [[ "$DRY_RUN" == true ]]; then
                log "[dry-run] Would remove $proto from project protocols dir"
            else
                rm -f "$proto_path"
                ok "Removed $proto from project protocols dir"
            fi
        fi
    done

    # Remove README if it was added by DS-EO install
    readme_path="${PROJECT_PROTOCOLS_DIR}/README.md"
    if [[ -f "$readme_path" ]]; then
        if grep -q 'DS-EO\|ds-eo-openclaw' "$readme_path" 2>/dev/null; then
            if [[ "$DRY_RUN" == true ]]; then
                log "[dry-run] Would remove $readme_path (DS-EO generated)"
            else
                rm -f "$readme_path"
                ok "Removed DS-EO README from project protocols dir"
            fi
        fi
    fi
else
    warn "Project protocols directory not found — nothing to clean."
fi

# ─── Step 4: Remove agent prompt files ──────────────────────────────

info "--- Step 4/4: Removing agent prompt files ---"
echo ""

AGENT_PROMPTS_DIR="$PKG_ROOT/docs/prompts/"
PROMPT_FILES=("ctos.md" "implementer.md" "reviewer.md")

if [[ -d "$AGENT_PROMPTS_DIR" ]]; then
    for prompt in "${PROMPT_FILES[@]}"; do
        prompt_path="${AGENT_PROMPTS_DIR}/${prompt}"
        if [[ -f "$prompt_path" ]]; then
            if grep -q 'DS-EO\|ds-eo-openclaw' "$prompt_path" 2>/dev/null; then
                if [[ "$DRY_RUN" == true ]]; then
                    log "[dry-run] Would remove $prompt (DS-EO generated)"
                else
                    rm -f "$prompt_path"
                    ok "Removed DS-EO prompt: $prompt"
                fi
            else
                warn "$prompt exists but is not a DS-EO file — leaving it alone"
            fi
        fi
    done
else
    warn "Agent prompts directory not found — nothing to clean."
fi

# ─── Cleanup (optional) ─────────────────────────────────────────────

if [[ "$PURGE_BACKUPS" == true ]]; then
    info "--- Cleanup: Removing DS-EO backup files ---"
    echo ""
    for bak in "$OPENCLAW_DIR/openclaw.json.bak.ds-eo-selfhost" \
               "$OPENCLAW_DIR/backups/ds-eo-openclaw-"*.json.bak; do
        if [[ -f "$bak" ]]; then
            if [[ "$DRY_RUN" == true ]]; then
                log "[dry-run] Would remove $bak"
            else
                rm -f "$bak"
                ok "Removed backup: $bak"
            fi
        fi
    done
fi

# ─── Final Summary ──────────────────────────────────────────────────

echo ""
if [[ "$DRY_RUN" == true ]]; then
    info "=== Dry Run Complete ==="
    echo "  No changes were made. The above shows what would be removed."
else
    info "=== Uninstall Complete ==="
    echo ""
    echo "  openclaw.json has been restored from backup."
    echo "  DS-EO protocol files have been cleaned up."
    echo ""

    if [[ "$PURGE_BACKUPS" == false ]]; then
        warn "Backup files preserved. To remove them, run with --purge-backups:"
        echo "  $(basename "$0") --confirm --purge-backups"
    fi

    echo ""
    echo "  Next steps:"
    echo "    1. Restart OpenClaw: openclaw gateway restart"
    echo "    2. Verify agents removed: cat $CONFIG_FILE | python3 -m json.tool"
    echo "    3. (Optional) Remove this package: rm -rf $PKG_ROOT"
fi
