#!/usr/bin/env bash
# deploy_agents.sh — Deploy DS-EO agent prompt files to target location
# Usage: deploy_agents.sh --target <path>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AGENTS_SRC="$PKG_ROOT/agents"

AGENT_FILES=(cto.md implementer.md pm.md reviewer.md)

show_help() {
    echo "Usage: deploy_agents.sh --target <path>"
    exit 0
}

if [[ "${1:-}" != "--target" ]]; then
    show_help
fi

TARGET_DIR="${2:?Usage: deploy_agents.sh --target <path>}"

if [ -z "$TARGET_DIR" ]; then
    echo "Error: Target directory required. Use --target <path>"
    exit 1
fi

mkdir -p "$TARGET_DIR"

echo "Deploying DS-EO agent prompts to: $TARGET_DIR"
echo ""

DEPLOYED=0
OVERWRITTEN=0

for agent_file in "${AGENT_FILES[@]}"; do
    SRC="$AGENTS_SRC/$agent_file"
    DST="$TARGET_DIR/$agent_file"

    if [ ! -f "$SRC" ]; then
        echo "  ✗ Source not found: $SRC (skipping)"
        continue
    fi

    if [ -f "$DST" ]; then
        cp "$DST" "${DST}.ds-eo-bak"
        OVERWRITTEN=$((OVERWRITTEN + 1))
        echo "  ✓ Overwritten: $agent_file (backup: ${DST}.ds-eo-bak)"
    else
        DEPLOYED=$((DEPLOYED + 1))
        echo "  ✓ Deployed: $agent_file"
    fi

    cp "$SRC" "$DST"
done

echo ""
echo "Agent prompt deployment complete:"
echo "  Deployed:   $DEPLOYED new files"
echo "  Overwritten: $OVERWRITTEN existing files (backed up with .ds-eo-bak)"
