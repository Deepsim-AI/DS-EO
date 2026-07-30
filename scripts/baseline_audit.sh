#!/usr/bin/env bash
# baseline_audit.sh — Detect file changes against v0.2-baseline
# Hard-fails (exit 1) if any modifications, additions, or deletions detected.
# Usage:
#   ./scripts/baseline_audit.sh              # Run audit
#   ./scripts/baseline_audit.sh --regenerate # Regenerate inventory from HEAD

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${REPO_ROOT}/logs"
LOG_FILE="${LOG_DIR}/baseline_audit.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
INVENTORY_FILE="${REPO_ROOT}/BASELINE_INVENTORY.txt"

mkdir -p "$LOG_DIR"

# ─── Regenerate Mode ──────────────────────────────────────
if [[ "${1:-}" == "--regenerate" ]]; then
    echo "Regenerating baseline inventory from HEAD..."
    cd "$REPO_ROOT"
    git ls-tree -r --name-only HEAD | while read -r file; do
        hash=$(sha256sum "$file" | awk '{print $1}')
        echo "$file $hash"
    done > "$INVENTORY_FILE"
    echo "Inventory written to $INVENTORY_FILE ($(wc -l < "$INVENTORY_FILE") entries)"
    exit 0
fi

# ─── Audit Mode ───────────────────────────────────────────

if [[ ! -f "$INVENTORY_FILE" ]]; then
    echo "Error: Baseline inventory not found at $INVENTORY_FILE"
    echo "Run with --regenerate first to create it."
    exit 2
fi

echo "=== Baseline Audit ===" > "$LOG_FILE"
echo "Timestamp: $TIMESTAMP" >> "$LOG_FILE"
echo "Repository: $REPO_ROOT" >> "$LOG_FILE"
echo "Inventory: $INVENTORY_FILE ($(wc -l < "$INVENTORY_FILE") entries)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

CHANGES_FOUND=0

# 1. Check for modified tracked files (content changed vs baseline)
echo "--- Modified Files ---" >> "$LOG_FILE"
while IFS= read -r file; do
    CURRENT_HASH=$(sha256sum "$file" | awk '{print $1}')
    BASELINE_HASH=$(grep "^${file} " "$INVENTORY_FILE" 2>/dev/null | awk '{print $2}' || echo "")
    if [[ -n "$BASELINE_HASH" && "$CURRENT_HASH" != "$BASELINE_HASH" ]]; then
        echo "MODIFIED: $file (baseline=$BASELINE_HASH current=$CURRENT_HASH)" >> "$LOG_FILE"
        CHANGES_FOUND=1
    fi
done < <(git ls-tree -r --name-only HEAD)

# 2. Check for new untracked files (potential leaks or additions)
echo "" >> "$LOG_FILE"
echo "--- New Untracked Files ---" >> "$LOG_FILE"
NEW_COUNT=0
while IFS= read -r file; do
    [[ -n "$file" ]] && echo "NEW: $file" >> "$LOG_FILE" && CHANGES_FOUND=1 && NEW_COUNT=$((NEW_COUNT + 1))
done < <(git ls-files --others --exclude-standard)
if [[ "$NEW_COUNT" -eq 0 ]]; then
    echo "(none)" >> "$LOG_FILE"
fi

# 3. Check for deleted tracked files (working tree vs HEAD)
echo "" >> "$LOG_FILE"
echo "--- Deleted Files ---" >> "$LOG_FILE"
DEL_COUNT=0
while IFS= read -r file; do
    [[ -n "$file" ]] && echo "DELETED: $file" >> "$LOG_FILE" && CHANGES_FOUND=1 && DEL_COUNT=$((DEL_COUNT + 1))
done < <(git diff --name-only HEAD)
if [[ "$DEL_COUNT" -eq 0 ]]; then
    echo "(none)" >> "$LOG_FILE"
fi

# Summary
echo "" >> "$LOG_FILE"
TOTAL=$(git ls-tree -r --name-only HEAD | wc -l)
if [[ "$CHANGES_FOUND" -eq 1 ]]; then
    echo "STATUS: FAIL — Baseline drift detected. Review $LOG_FILE for details." >> "$LOG_FILE"
    cat "$LOG_FILE"
    exit 1
else
    echo "STATUS: PASS — All $TOTAL tracked files match baseline." >> "$LOG_FILE"
    cat "$LOG_FILE"
    exit 0
fi
