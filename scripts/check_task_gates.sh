#!/usr/bin/env bash
# check_task_gates.sh — Verify gate compliance for a TASK directory
# Usage: ./scripts/check_task_gates.sh <TASK_DIR> [required_artifacts...]
# Example: ./scripts/check_task_gates.sh docs/development/reports/TASK_DS_EO_024
# With no extra args, checks all required gate artifacts.

set -euo pipefail

TASK_DIR="${1:-}"
if [[ -z "$TASK_DIR" ]]; then
  echo "Usage: $0 <task_directory> [optional_required_artifact ...]"
  exit 1
fi

# Resolve to absolute path
TASK_DIR="$(cd "$(dirname "$TASK_DIR")" && pwd)/$(basename "$TASK_DIR")"

if [[ ! -d "$TASK_DIR" ]]; then
  echo "ERROR: Directory '$TASK_DIR' does not exist."
  exit 1
fi

# Collect extra args (artifacts) — these are args 2 onward
shift
EXTRA_ARGS=("$@")

REQUIRED=()
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  for a in "${EXTRA_ARGS[@]}"; do
    REQUIRED+=("$a")
  done
else
  REQUIRED=(
    CTO_PLAN.md
    IMPLEMENTATION_REPORT.md
    REVIEW_REPORT.md
    CTO_APPROVAL.md
    TASK_COMPLETION_AUDIT.md
  )
fi

MISSING=()
EMPTY=()
BLOCKED_FILE=""

# Check for BLOCKED file
if [[ -f "$TASK_DIR/BLOCKED_BY_MISSING_ARTIFACTS.md" ]]; then
  BLOCKED_FILE="$TASK_DIR/BLOCKED_BY_MISSING_ARTIFACTS.md"
fi

for artifact in "${REQUIRED[@]}"; do
  filepath="$TASK_DIR/$artifact"
  if [[ ! -e "$filepath" ]]; then
    MISSING+=("$artifact")
  elif [[ ! -s "$filepath" ]]; then
    EMPTY+=("$artifact")
  fi
done

# Output results
echo "=== Gate Compliance Check: $(basename "$TASK_DIR") ==="
echo "Directory: $TASK_DIR"
echo ""

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "❌ MISSING artifacts (${#MISSING[@]}):"
  for m in "${MISSING[@]}"; do
    echo "   - $m"
  done
fi

if [[ ${#EMPTY[@]} -gt 0 ]]; then
  echo "⚠️  EMPTY (non-empty required) artifacts (${#EMPTY[@]}):"
  for e in "${EMPTY[@]}"; do
    echo "   - $e"
  done
fi

if [[ -n "$BLOCKED_FILE" ]]; then
  echo ""
  echo "🔒 Task is BLOCKED:"
  head -5 "$BLOCKED_FILE" | sed 's/^/   /'
  echo "   ..."
fi

# Check gate order if all files present
GATES_OK=true
if [[ ${#MISSING[@]} -eq 0 ]]; then
  # Verify REVIEW_REPORT exists before CTO_APPROVAL
  if [[ -f "$TASK_DIR/CTO_APPROVAL.md" ]] && [[ ! -f "$TASK_DIR/REVIEW_REPORT.md" ]]; then
    echo "❌ GATE ORDER VIOLATION: CTO_APPROVAL.md exists but REVIEW_REPORT.md does not (G4 before G3)"
    GATES_OK=false
  fi

  # Check TASK_COMPLETION_AUDIT consistency if present
  if [[ -f "$TASK_DIR/TASK_COMPLETION_AUDIT.md" ]]; then
    audit_status=$(grep "Final Status:" "$TASK_DIR/TASK_COMPLETION_AUDIT.md" 2>/dev/null | head -1 | sed 's/.*Final Status: *//' || true)
    if [[ "$audit_status" == *"BLOCKED"* ]] || [[ "$audit_status" == *"NOT EXECUTED"* ]]; then
      echo "⚠️  TASK_COMPLETION_AUDIT.md marks this task as '$audit_status' — gates may not be complete"
    fi
  fi

  if $GATES_OK && [[ ${#MISSING[@]} -eq 0 ]] && [[ ${#EMPTY[@]} -eq 0 ]]; then
    echo "✅ All required artifacts present and non-empty"
  fi
fi

echo ""
if [[ ${#MISSING[@]} -gt 0 ]] || [[ ${#EMPTY[@]} -gt 0 ]]; then
  echo "Result: BLOCKED — fix missing/empty artifacts before proceeding"
  exit 2
else
  echo "Result: PASS — all gates compliant"
  exit 0
fi
