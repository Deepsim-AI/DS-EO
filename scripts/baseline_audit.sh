#!/usr/bin/env bash
# baseline_audit.sh — Detect file changes against v0.2-baseline
# Hard-fails (exit 1) if any modifications, additions, or deletions detected.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${REPO_ROOT}/logs"
LOG_FILE="${LOG_DIR}/baseline_audit.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$LOG_DIR"

echo "=== Baseline Audit ===" > "$LOG_FILE"
echo "Timestamp: $TIMESTAMP" >> "$LOG_FILE"
echo "Repository: $REPO_ROOT" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

CHANGES_FOUND=0

# 1. Check for modified tracked files (content changed vs baseline)
echo "--- Modified Files ---" >> "$LOG_FILE"
while IFS= read -r file; do
    CURRENT_HASH=$(sha256sum "$file" | awk '{print $1}')
    BASELINE_HASH=$(grep "^${file} " /tmp/baseline_sha_inventory.txt 2>/dev/null | awk '{print $2}' || echo "")
    if [[ -n "$BASELINE_HASH" && "$CURRENT_HASH" != "$BASELINE_HASH" ]]; then
        echo "MODIFIED: $file" >> "$LOG_FILE"
        CHANGES_FOUND=1
    fi
done < <(git ls-tree -r --name-only HEAD)

# 2. Check for new untracked files (potential leaks or additions)
echo "" >> "$LOG_FILE"
echo "--- New Untracked Files ---" >> "$LOG_FILE"
while IFS= read -r file; do
    [[ -n "$file" ]] && echo "NEW: $file" >> "$LOG_FILE" && CHANGES_FOUND=1
done < <(git ls-files --others --exclude-standard)

# 3. Check for deleted tracked files
echo "" >> "$LOG_FILE"
echo "--- Deleted Files ---" >> "$LOG_FILE"
while IFS= read -r file; do
    [[ -n "$file" ]] && echo "DELETED: $file" >> "$LOG_FILE" && CHANGES_FOUND=1
done < <(git diff --name-only HEAD)

# Summary
echo "" >> "$LOG_FILE"
if [[ "$CHANGES_FOUND" -eq 1 ]]; then
    echo "STATUS: FAIL — Baseline drift detected. Review $LOG_FILE for details." >> "$LOG_FILE"
    cat "$LOG_FILE"
    exit 1
else
    TOTAL=$(git ls-tree -r --name-only HEAD | wc -l)
    echo "STATUS: PASS — All $TOTAL tracked files match baseline." >> "$LOG_FILE"
    cat "$LOG_FILE"
    exit 0
fi
