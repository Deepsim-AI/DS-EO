#!/usr/bin/env bash
# backup_openclaw_config.sh — Create a timestamped backup of openclaw.json
# Usage: backup_openclaw_config.sh [--target <path>]

set -euo pipefail

OPENCLAW_DIR="${DS_EO_OPENCLAW_DIR:-$HOME/.openclaw}"
CONFIG_FILE="${2:-$OPENCLAW_DIR/openclaw.json}"
BACKUP_DIR="$OPENCLAW_DIR/backups"

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%dT%H%M%S)
BACKUP_PATH="$BACKUP_DIR/ds-eo-openclaw-${TIMESTAMP}.json.bak"

cp "$CONFIG_FILE" "$BACKUP_PATH"
echo "Backup created: $BACKUP_PATH"

# Also back up any existing protocol files that will be overwritten
if [ -d "$OPENCLAW_DIR/protocols/" ]; then
    for proto in approval communication completion delegation handoff review; do
        if [ -f "$OPENCLAW_DIR/protocols/${proto}_protocol.md" ]; then
            cp "$OPENCLAW_DIR/protocols/${proto}_protocol.md" \
               "$OPENCLAW_DIR/protocols/${proto}_protocol.md.ds-eo-bak" 2>/dev/null || true
        fi
    done
fi

echo "Protocol backups created (if applicable)"
