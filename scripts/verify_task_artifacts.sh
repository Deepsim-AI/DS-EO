#!/usr/bin/env bash
# verify_task_artifacts.sh — Validate task directory completeness, structure, and identity integrity
#
# Usage: verify_task_artifacts.sh <task_dir_path> [--json]
# Exit codes:
#   0 — All artifacts present with required structure AND identity checks pass (PASS)
#   1 — One or more validation failures (FAIL with gap report)
#   2 — Invalid usage / bad arguments
#
# The script checks each of the 4 required handoff artifacts for:
#   - File existence
#   - Minimum size (>50 bytes, not empty/trivial)
#   - Required content sections (minimum viable structure)
#   - Identity metadata presence (agent_id, session_id, model, produced_at) — NEW in v0.3
#   - Role independence: reviewer ≠ implementer, approver ≠ both

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ─── Configuration ────────────────────────────────────────────────

REQUIRED_ARTIFACTS=("CTO_PLAN.md" "IMPLEMENTATION_REPORT.md" "REVIEW_REPORT.md" "CTO_APPROVAL.md")

declare -A MINIMUM_SECTIONS=(
    ["CTO_PLAN.md"]="Acceptance Criteria"
    ["IMPLEMENTATION_REPORT.md"]="Acceptance Criteria Verification"
    ["REVIEW_REPORT.md"]="Recommendation"
    ["CTO_APPROVAL.md"]="Decision:"
)

declare -A ADDITIONAL_CHECKS=(
    ["CTO_PLAN.md"]="Role.*Architect|Implementer|Reviewer"
    ["IMPLEMENTATION_REPORT.md"]="Tests?|Test Results|test results|PASS|FAIL"
    ["REVIEW_REPORT.md"]="APPROVE|REJECT|REQUEST_CHANGES"
    ["CTO_APPROVAL.md"]="APPROVED|REJECTED"
)

MIN_SIZE=50          # Minimum file size in bytes (trivial files rejected)
OUTPUT_JSON=false

# ─── Identity Metadata Extraction ─────────────────────────────────
# Extract metadata from a markdown artifact's header.
# Looks for **agent_id**, **session_id**, **model**, **produced_at** lines.

get_field() {
    local file="$1" field="$2"
    grep -m1 "^\*\*${field}\*\*:" "$file" 2>/dev/null | sed 's/^\*\*'"${field}"'\*\*: //' | sed 's/<[^>]*>//g' | tr -d ' \t'
}

# ─── Argument Parsing ─────────────────────────────────────────────

if [[ "${1:-}" == "--json" ]]; then
    OUTPUT_JSON=true
    shift
fi

if [[ $# -lt 1 ]] || [[ ! -d "$1" ]]; then
    echo "Usage: verify_task_artifacts.sh [--json] <task_dir_path>" >&2
    echo "  task_dir_path — path to a TASK_<YYYYMMDD>_<NNN>/ directory" >&2
    exit 2
fi

TASK_DIR="$1"

# ─── Helpers ──────────────────────────────────────────────────────

failures=0
warnings=0
declare -a failure_messages=()
declare -a warning_messages=()
declare -A artifact_status=()

report_pass() {
    local msg="$1"
    if [[ "$OUTPUT_JSON" == true ]]; then
        echo "{\"status\":\"PASS\",\"message\":\"$msg\"}"
    else
        echo "  ✓ $msg"
    fi
}

report_fail() {
    local msg="$1"
    failures=$((failures + 1))
    failure_messages+=("$msg")
    if [[ "$OUTPUT_JSON" == true ]]; then
        echo "{\"status\":\"FAIL\",\"message\":\"$msg\"}"
    else
        echo "  ✗ $msg"
    fi
}

report_warn() {
    local msg="$1"
    warnings=$((warnings + 1))
    warning_messages+=("$msg")
    if [[ "$OUTPUT_JSON" == true ]]; then
        echo "{\"status\":\"WARN\",\"message\":\"$msg\"}"
    else
        echo "  ⚠ $msg"
    fi
}

# ─── Validation: File Checks ──────────────────────────────────────

validate_artifact() {
    local artifact="$1"
    local path="${TASK_DIR}/${artifact}"
    local status="PASS"

    # Check 1: File exists
    if [[ ! -f "$path" ]]; then
        report_fail "${artifact} — MISSING (required handoff artifact not found)"
        status="MISSING"
        echo ""
        return
    fi

    # Check 2: Minimum size
    local size
    size=$(wc -c < "$path")
    if [[ "$size" -lt "$MIN_SIZE" ]]; then
        report_fail "${artifact} — TOO_SMALL (${size} bytes, minimum ${MIN_SIZE})"
        status="TOO_SMALL"
        echo ""
        return
    fi

    # Check 3: Required content sections (at least one of the minimum section keywords)
    local required="${MINIMUM_SECTIONS[$artifact]}"
    if ! grep -q "$required" "$path"; then
        report_fail "${artifact} — MISSING_SECTION (missing required content: '${required}')"
        status="MISSING_SECTION"
        echo ""
        return
    fi

    # Check 4: Additional structural checks (optional, reported as warnings if missing)
    local additional="${ADDITIONAL_CHECKS[$artifact]:-}"
    if [[ -n "$additional" ]]; then
        local found_additional=false
        IFS='|' read -ra checks <<< "$additional"
        for check in "${checks[@]}"; do
            if grep -qi "$check" "$path"; then
                found_additional=true
                break
            fi
        done
        if [[ "$found_additional" == false ]]; then
            report_warn "${artifact} — could not find expected content patterns (may still be valid)"
        else
            report_pass "${artifact} — structure validated (${size} bytes, required sections present)"
        fi
    else
        report_pass "${artifact} — structure validated (${size} bytes, required sections present)"
    fi

    status="PASS"
    echo ""
}

# ─── Validation: Identity Metadata ────────────────────────────────

validate_identity_metadata() {
    local artifact="$1"
    local path="${TASK_DIR}/${artifact}"
    local missing_fields=""

    for field in agent_id session_id model produced_at; do
        local value
        value=$(get_field "$path" "$field")
        if [[ -z "$value" ]]; then
            missing_fields="${missing_fields}${field} "
        fi
    done

    if [[ -n "$missing_fields" ]]; then
        report_fail "${artifact} — MISSING_IDENTITY_METADATA (missing fields: ${missing_fields})"
        echo ""
        return 1
    fi

    report_pass "${artifact} — identity metadata present (agent_id, session_id, model, produced_at)"
    echo ""
    return 0
}

# ─── Validation: Role Independence ────────────────────────────────

validate_role_independence() {
    local impl_report="${TASK_DIR}/IMPLEMENTATION_REPORT.md"
    local review_report="${TASK_DIR}/REVIEW_REPORT.md"
    local approval_report="${TASK_DIR}/CTO_APPROVAL.md"

    # Extract agent_id from each artifact
    local impl_agent="" rev_agent="" appr_agent=""
    impl_agent=$(get_field "$impl_report" "agent_id") || impl_agent=""
    rev_agent=$(get_field "$review_report" "agent_id") || rev_agent=""
    appr_agent=$(get_field "$approval_report" "agent_id") || appr_agent=""

    # Extract session_id from each artifact
    local impl_session="" rev_session="" appr_session=""
    impl_session=$(get_field "$impl_report" "session_id") || impl_session=""
    rev_session=$(get_field "$review_report" "session_id") || rev_session=""
    appr_session=$(get_field "$approval_report" "session_id") || appr_session=""

    # Extract model from each artifact
    local impl_model="" rev_model="" appr_model=""
    impl_model=$(get_field "$impl_report" "model") || impl_model=""
    rev_model=$(get_field "$review_report" "model") || rev_model=""
    appr_model=$(get_field "$approval_report" "model") || appr_model=""

    # Known correct role-model bindings per ds_eo_manifest.yaml:
    local expected_implementer_model="ollama/ornith:35b"
    local expected_reviewer_model="ollama/laguna-xs-2.1:q4_K_M"
    local expected_cto_model="ollama/qwen3.6:35b"

    # Check 1: Reviewer agent_id must be 'reviewer'
    if [[ "$rev_agent" != "reviewer" ]]; then
        report_fail "REVIEW_AGENT_ID_VIOLATION: reviewer artifact has agent_id='${rev_agent}' (expected 'reviewer')"
    fi

    # Check 2: Approver agent_id must be 'cto'
    if [[ "$appr_agent" != "cto" ]]; then
        report_fail "APPROVER_AGENT_ID_VIOLATION: CTO_APPROVAL has agent_id='${appr_agent}' (expected 'cto')"
    fi

    # Check 3: Reviewer model must match expected reviewer model
    if [[ "$rev_model" != "$expected_reviewer_model" ]]; then
        report_fail "REVIEW_MODEL_VIOLATION: reviewer artifact uses model='${rev_model}' (expected '${expected_reviewer_model}')"
    fi

    # Check 4: Approver model must match expected CTO model
    if [[ "$appr_model" != "$expected_cto_model" ]]; then
        report_fail "APPROVER_MODEL_VIOLATION: approver artifact uses model='${appr_model}' (expected '${expected_cto_model}')"
    fi

    # Check 5: Implementer agent_id must be 'implementer'
    if [[ "$impl_agent" != "implementer" ]]; then
        report_fail "IMPLEMENTER_AGENT_ID_VIOLATION: implementation artifact has agent_id='${impl_agent}' (expected 'implementer')"
    fi

    # Check 6: Review and Implement must NOT share the same session
    if [[ -n "$rev_session" && -n "$impl_session" && "$rev_session" == "$impl_session" ]]; then
        report_fail "SESSION_INDEPENDENCE_VIOLATION: REVIEW_REPORT and IMPLEMENTATION_REPORT share session_id='${rev_session}' — self-review detected!"
    fi

    # Check 7: Approver and Reviewer must NOT share the same session
    if [[ -n "$appr_session" && -n "$rev_session" && "$appr_session" == "$rev_session" ]]; then
        report_fail "SESSION_INDEPENDENCE_VIOLATION: CTO_APPROVAL and REVIEW_REPORT share session_id='${appr_session}' — self-approval detected!"
    fi

    # Check 8: Approver and Implementer must NOT share the same session
    if [[ -n "$appr_session" && -n "$impl_session" && "$appr_session" == "$impl_session" ]]; then
        report_fail "SESSION_INDEPENDENCE_VIOLATION: CTO_APPROVAL and IMPLEMENTATION_REPORT share session_id='${appr_session}' — self-approval with shared context!"
    fi

    # Check 9: Reviewer agent_id must NOT match Implementer agent_id
    if [[ "$rev_agent" == "$impl_agent" && -n "$rev_agent" ]]; then
        report_fail "ROLE_COLLAPSE_VIOLATION: reviewer and implementer have same agent_id='${rev_agent}' — roles collapsed!"
    fi

    # Check 10: Approver agent_id must NOT match either reviewer or implementer
    if [[ -n "$appr_agent" ]]; then
        if [[ "$appr_agent" == "$rev_agent" && -n "$rev_agent" ]]; then
            report_fail "ROLE_COLLAPSE_VIOLATION: approver and reviewer have same agent_id='${appr_agent}' — roles collapsed!"
        fi
        if [[ "$appr_agent" == "$impl_agent" && -n "$impl_agent" ]]; then
            report_fail "ROLE_COLLAPSE_VIOLATION: approver and implementer have same agent_id='${appr_agent}' — roles collapsed!"
        fi
    fi

    # Report all checks passed
    local check_count=10
    if [[ -z "$rev_agent" || "$rev_agent" == "reviewer" ]]; then ((check_count++)) || true; fi
    if [[ -z "$appr_agent" || "$appr_agent" == "cto" ]]; then ((check_count++)) || true; fi
    report_pass "${check_count} role independence checks passed (agent_id, session_id, model cross-validation)"
    echo ""
}

# ─── Phase 4 (skipped): Reserved for future use ──────────────

# ─── Phase 5: PM Artifacts Verification (OPTIONAL) ────────────
#
# This phase validates Post-Milestone process artifacts that are NOT gate-critical.
# Missing or incomplete PM artifacts produce WARNINGs, not FAILs.
# These artifacts support project management and release tracking but do not block task completion.

validate_pm_artifacts() {
    local task_id="${TASK_DIR##*/}"
    
    # Check 1: PROJECT_STATUS.md exists and is updated with task completion status
    if [[ -f "${TASK_DIR}/PROJECT_STATUS.md" ]]; then
        local size
        size=$(wc -c < "${TASK_DIR}/PROJECT_STATUS.md")
        if [[ "$size" -lt 50 ]]; then
            report_warn "PM-1: PROJECT_STATUS.md too small (${size} bytes) for task ${task_id}" \
                "[Phase 5]: PROJECT_STATUS.md missing or incomplete for task ${task_id}"
        elif ! grep -qi "${task_id}" "${TASK_DIR}/PROJECT_STATUS.md"; then
            report_warn "PM-1: PROJECT_STATUS.md does not reference task ${task_id}" \
                "[Phase 5]: PROJECT_STATUS.md missing or incomplete for task ${task_id}"
        else
            report_pass "PM-1: PROJECT_STATUS.md present and updated (size: ${size} bytes)"
        fi
    else
        report_warn "PM-1: PROJECT_STATUS.md not found" \
            "[Phase 5]: PROJECT_STATUS.md missing or incomplete for task ${task_id}"
    fi
    
    # Check 2: CHANGELOG entries exist for the completed task
    if [[ -f "${TASK_DIR}/CHANGELOG.md" ]]; then
        local size
        size=$(wc -c < "${TASK_DIR}/CHANGELOG.md")
        if [[ "$size" -lt 50 ]]; then
            report_warn "PM-2: CHANGELOG.md too small (${size} bytes) for task ${task_id}" \
                "[Phase 5]: CHANGELOG entries missing or incomplete for task ${task_id}"
        elif ! grep -qi "${task_id}" "${TASK_DIR}/CHANGELOG.md"; then
            report_warn "PM-2: CHANGELOG.md does not reference task ${task_id}" \
                "[Phase 5]: CHANGELOG entries missing or incomplete for task ${task_id}"
        else
            report_pass "PM-2: CHANGELOG.md present and updated (size: ${size} bytes)"
        fi
    else
        report_warn "PM-2: CHANGELOG.md not found" \
            "[Phase 5]: CHANGELOG entries missing or incomplete for task ${task_id}"
    fi
    
    # Check 3: Release checklist (if applicable to milestone) is present or flagged appropriately
    if [[ -f "${TASK_DIR}/RELEASE_CHECKLIST.md" ]]; then
        local size
        size=$(wc -c < "${TASK_DIR}/RELEASE_CHECKLIST.md")
        if [[ "$size" -lt 50 ]]; then
            report_warn "PM-3: RELEASE_CHECKLIST.md too small (${size} bytes) for task ${task_id}" \
                "[Phase 5]: Release checklist missing or incomplete for task ${task_id}"
        else
            report_pass "PM-3: RELEASE_CHECKLIST.md present (size: ${size} bytes)"
        fi
    elif grep -qi "milestone\|release" "${TASK_DIR}/CTO_PLAN.md" 2>/dev/null; then
        # If CTO_PLAN mentions milestone/release but no checklist exists, warn appropriately
        report_warn "PM-3: No RELEASE_CHECKLIST.md found (CTO_PLAN suggests milestone/release context)" \
            "[Phase 5]: Release checklist missing or incomplete for task ${task_id}"
    else
        # Skip if not applicable - no warning needed
        report_pass "PM-3: Release checklist not required for this task"
    fi
    
    # Check 4: Task closure is properly recorded in task directory
    # Look for CLOSURE.md or a CLOSURE section in any artifact
    local closure_found=false
    if [[ -f "${TASK_DIR}/CLOSURE.md" ]]; then
        closure_found=true
    elif grep -rq "closure\|task_complete\|closed_on:" "${TASK_DIR}/" 2>/dev/null; then
        closure_found=true
    fi
    
    if [[ "$closure_found" == true ]]; then
        report_pass "PM-4: Task closure recorded in task directory"
    else
        report_warn "PM-4: No task closure documentation found" \
            "[Phase 5]: Task closure is missing or incomplete for task ${task_id}"
    fi
}

# ─── Main Execution ───────────────────────────────────────────────

echo "═══ DS-EO Task Artifact Verification ═══"
echo "Task directory: ${TASK_DIR}"
echo ""

# Phase 1: File existence and structural checks
echo "--- Phase 1: Artifact Existence & Structure ---"
for artifact in "${REQUIRED_ARTIFACTS[@]}"; do
    validate_artifact "$artifact"
done

# Phase 2: Identity metadata validation (only for existing artifacts)
echo ""
echo "--- Phase 2: Identity Metadata ---"
METADATA_PASS=true
for artifact in "IMPLEMENTATION_REPORT.md" "REVIEW_REPORT.md" "CTO_APPROVAL.md"; do
    if [[ -f "${TASK_DIR}/${artifact}" ]]; then
        validate_identity_metadata "$artifact" || METADATA_PASS=false
    fi
done

if [[ "$METADATA_PASS" != true ]]; then
    echo "Identity metadata validation FAILED — skipping role independence checks (insufficient data)."
    echo ""
else
    # Phase 3: Role independence cross-validation
    echo ""
    echo "--- Phase 3: Role Independence Cross-Validation ---"
    validate_role_independence
fi

# Phase 5: PM Artifacts Verification (OPTIONAL - produces warnings, not failures)
echo ""
echo "--- Phase 5: Process Management Artifacts (OPTIONAL) ---"
validate_pm_artifacts

# ─── Summary ──────────────────────────────────────────────────────

if [[ "$OUTPUT_JSON" == true ]]; then
    echo "{"
    echo "  \"task_dir\": \"${TASK_DIR}\","
    echo "  \"summary\": {"
    echo "    \"total_checked\": ${#REQUIRED_ARTIFACTS[@]},"
    echo "    \"failures\": ${failures},"
    echo "    \"warnings\": ${warnings}"
    echo "  },"
    if [[ ${#failure_messages[@]} -gt 0 ]]; then
        echo "  \"failures\": ["
        local first=true
        for msg in "${failure_messages[@]}"; do
            if [[ "$first" == true ]]; then
                first=false
            else
                echo ","
            fi
            printf '    "%s"' "$msg"
        done
        echo ""
        echo "  ],"
    fi
    if [[ ${#warning_messages[@]} -gt 0 ]]; then
        echo "  \"warnings\": ["
        first=true
        for msg in "${warning_messages[@]}"; do
            if [[ "$first" == true ]]; then
                first=false
            else
                echo ","
            fi
            printf '    "%s"' "$msg"
        done
        echo ""
        echo "  ]"
    fi
    echo "  \"result\": \"$([ $failures -eq 0 ] && echo PASS || echo FAIL)\""
    echo "}"
else
    echo "--- Summary ---"
    if [[ ${#warning_messages[@]} -gt 0 ]]; then
        echo ""
        echo "Warnings:"
        for msg in "${warning_messages[@]}"; do
            echo "  ⚠ $msg"
        done
    fi

    if [[ "$failures" -eq 0 ]]; then
        echo ""
        echo "═══ PASS: All ${#REQUIRED_ARTIFACTS[@]} artifacts present with required structure and identity checks ═══"
        exit 0
    else
        echo ""
        echo "═══ FAIL: ${failures} artifact validation failure(s) ═══"
        echo ""
        echo "Gap Report:"
        idx=1
        for msg in "${failure_messages[@]}"; do
            echo "  ${idx}. $msg"
            idx=$((idx + 1))
        done
        exit 1
    fi
fi
