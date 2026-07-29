#!/usr/bin/env bash
# deploy_protocols.sh — Deploy DS-EO protocol files to target location
# Usage:
#   deploy_protocols.sh --target <path>           # Deploy protocols to target
#   deploy_protocols.sh --rollback                # Remove DS-EO protocols, restore backups

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROTOCOLS_SRC="$PKG_ROOT/protocols"

# Protocol files to deploy (exclude README.md which is informational)
PROTO_FILES=(
    approval_protocol.md
    communication_protocol.md
    completion_protocol.md
    delegation_protocol.md
    handoff_protocol.md
    review_protocol.md
)

show_help() {
    echo "Usage:"
    echo "  deploy_protocols.sh --target <path>   Deploy protocols to target directory"
    echo "  deploy_protocols.sh --rollback        Remove DS-EO protocols, restore backups"
    exit 0
}

# ─── Rollback Mode ────────────────────────────────────────────────

if [[ "${1:-}" == "--rollback" ]]; then
    TARGET_DIR="${2:?Usage: deploy_protocols.sh --rollback [--target <path>]}"

    if [ -z "$TARGET_DIR" ]; then
        echo "Error: Target directory required for rollback. Use --target <path>"
        exit 1
    fi

    echo "Rolling back DS-EO protocols from: $TARGET_DIR"

    for proto in "${PROTO_FILES[@]}"; do
        TARGET_FILE="$TARGET_DIR/$proto"
        BACKUP_FILE="${TARGET_FILE}.ds-eo-bak"

        if [ -f "$BACKUP_FILE" ]; then
            mv "$BACKUP_FILE" "$TARGET_FILE"
            echo "  Restored: $TARGET_FILE (from .ds-eo-bak backup)"
        elif [ -f "$TARGET_FILE" ]; then
            echo "  Removed:  $TARGET_FILE (no backup found — file was not from DS-EO install)"
            # Don't delete files that weren't installed by DS-EO
        fi
    done

    echo "Rollback complete."
    exit 0
fi

# ─── Deploy Mode ──────────────────────────────────────────────────

if [[ "${1:-}" == "--target" ]]; then
    TARGET_DIR="${2:?Usage: deploy_protocols.sh --target <path>}"

    if [ -z "$TARGET_DIR" ]; then
        echo "Error: Target directory required. Use --target <path>"
        exit 1
    fi

    # Create target directory if it doesn't exist
    mkdir -p "$TARGET_DIR"

    echo "Deploying DS-EO protocols to: $TARGET_DIR"
    echo ""

    DEPLOYED=0
    SKIPPED=0
    OVERWRITTEN=0

    for proto in "${PROTO_FILES[@]}"; do
        SRC="$PROTOCOLS_SRC/$proto"
        DST="$TARGET_DIR/$proto"

        if [ ! -f "$SRC" ]; then
            echo "  ✗ Source not found: $SRC (skipping)"
            continue
        fi

        if [ -f "$DST" ]; then
            # File exists — back up and overwrite
            cp "$DST" "${DST}.ds-eo-bak"
            OVERWRITTEN=$((OVERWRITTEN + 1))
            echo "  ✓ Overwritten: $proto (backup: ${DST}.ds-eo-bak)"
        else
            DEPLOYED=$((DEPLOYED + 1))
            echo "  ✓ Deployed: $proto"
        fi

        cp "$SRC" "$DST"
    done

    # Also deploy README.md if target is a fresh protocols directory
    if [ -f "$PROTOCOLS_SRC/README.md" ]; then
        DST_README="$TARGET_DIR/README.md"
        if [ ! -f "$DST_README" ]; then
            cp "$PROTOCOLS_SRC/README.md" "$DST_README"
        fi
    fi

    echo ""
    echo "Deployment complete:"
    echo "  Deployed:   $DEPLOYED new files"
    echo "  Overwritten: $OVERWRITTEN existing files (backed up with .ds-eo-bak)"
    exit 0
fi

show_help
