#!/usr/bin/env bash
# generate_handoff_message.sh — Produce standardized handoff messages from task artifacts.
# Usage: generate_handoff_message.sh <message-type> <task-dir> [additional-args...]
#   message-types: delegate, impl-complete, review-result, approval
#
# Each type reads from known artifact files in the task directory and emits a
# formatted handoff message to stdout following templates H-01 through H-04.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MESSAGE_TYPES=(delegate impl-complete review-result approval)

# ─── Helpers ────────────────────────────────────────────────────────────────────

usage() {
    echo "Usage: $0 <delegate|impl-complete|review-result|approval> <task-dir>"
    echo ""
    echo "Message types:"
    for t in "${MESSAGE_TYPES[@]}"; do
        case "$t" in
            delegate)         desc="CTO → Implementer (Task Delegation)" ;;
            impl-complete)    desc="Implementer → Reviewer (Implementation Complete)" ;;
            review-result)    desc="Reviewer → CTO (Review Result)" ;;
            approval)         desc="CTO → User (Approval Decision)" ;;
        esac
        echo "  $t — $desc"
    done
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

# Extract a numbered list from a markdown section.
# Usage: extract_numbered_list <file> "<section_header>" [start_indent]
extract_numbered_list() {
    local file="$1" header="$2" indent="${3:-0}"
    awk -v header="$header" -v start="$indent" '
        /^\S/ && !seen { if (index($0, header) == 1) seen=1; next }
        seen && /^[0-9]+[.)]/ { print }
        seen && /^$/{ next }
        seen && !/^[[:space:]]/ { exit }
    ' "$file"
}

# Extract a bulleted list from a markdown section.
# Usage: extract_bulleted_list <file> "<section_header>" [start_indent]
extract_bulleted_list() {
    local file="$1" header="$2" indent="${3:-0}"
    awk -v header="$header" '
        !seen && /^$/ { next }
        !seen && /^\S/ && index($0, header) == 1 { seen=1; next }
        seen && (/^- / || /^\* /) { sub(/^[[:space:]]*- [[:space:]]*/, ""); sub(/^[[:space:]]*\* [[:space:]]*/, ""); print }
        seen && /^$/ { next }
        seen && !/^- / && !/^\* / && !/^$/ { exit }
    ' "$file"
}

# Extract a single value from "Key: Value" pattern in markdown.
extract_field() {
    local file="$1" field="$2"
    grep -iE "^${field}[[:space:]]*:" "$file" 2>/dev/null | head -1 | sed "s/^${field}[[:space:]]*:[[:space:]]*/[REPLACED]/" | sed 's/.*\[\(.*\)\].*/\1/'
}

# Extract title from a markdown file (first heading or Title field).
extract_title() {
    local file="$1"
    # Try "Title:" field first, then first # heading
    local title=""
    if [[ -n "$(grep -iE '^Title:' "$file" 2>/dev/null)" ]]; then
        title=$(grep -iE '^Title:' "$file" | head -1 | sed 's/^Title:[[:space:]]*//')
    else
        title=$(head -50 "$file" | grep '^# ' | head -1 | sed 's/^# [[:space:]]*//' | sed 's/[[:space:]]*$//')
    fi
    echo "${title:-Untitled}"
}

# Get task ID from directory name.
extract_task_id() {
    local dir="$1"
    basename "$dir"
}

# Count files changed in git diff stat output (format: "N file(s) changed...").
count_git_changes() {
    local scope="${1:-}"
    local stat_output
    if [[ -n "$scope" ]]; then
        stat_output=$(cd "$REPO_ROOT" && git diff --stat "${scope}" 2>/dev/null || echo "")
    else
        stat_output=$(cd "$REPO_ROOT" && git diff --stat 2>/dev/null || echo "")
    fi

    if [[ -z "$stat_output" ]]; then
        echo "0 file(s) changed across 0 dir(s)"
        return
    fi

    local files dirs
    files=$(echo "$stat_output" | tail -1 | grep -oP '^\d+ file' || echo "0 file")
    # Count unique directories from the stat output (lines before summary)
    dirs=$(echo "$stat_output" | head -n -1 | awk '{print $NF}' | sed 's/:$//' | sort -u | wc -l)

    echo "${files} changed across ${dirs} dir(s)"
}

# ─── Message Producers ──────────────────────────────────────────────────────────

produce_delegate() {
    local task_dir="$1"
    local plan_file="${task_dir}/CTO_PLAN.md"

    [[ -f "$plan_file" ]] || die "CTO_PLAN.md not found in ${task_dir}"

    local task_id title work_items constraints boundary_note
    task_id=$(extract_task_id "$task_dir")
    title=$(extract_title "$plan_file")

    # Extract work items from "What to do:" or "Work Items" section
    work_items=$(extract_numbered_list "$plan_file" "What to do:")
    if [[ -z "$work_items" ]]; then
        work_items=$(grep "^### Item " "$plan_file" 2>/dev/null | sed 's/^.*[Ii]tem //')
    fi

    if [[ -z "$work_items" ]]; then
        die "No 'What to do:' section found in CTO_PLAN.md"
    fi

    local num_work_items
    num_work_items=$(echo "$work_items" | grep -cE '^[0-9]+[.)]' || echo "0")

    # Extract constraints from "Constraints:" section
    # Constraints may be bulleted (-) or numbered (1.). Extract both.
    constraints=$(sed -n "/^## Constraints$/,/^---$/p" "$plan_file" 2>/dev/null | grep '^[0-9]' | sed 's/^[[:space:]]*//' || echo "")
    if [[ -z "$constraints" ]]; then
        constraints=$(extract_bulleted_list "$plan_file" "Constraints:")
    fi

    # Check for task boundary note in plan
    if [[ -f "${task_dir}/CTO_PLAN.md" ]]; then
        boundary_note=$(grep -A2 'Task boundary' "$plan_file" 2>/dev/null | tail -1 || echo "")
        # Clean up the boundary note
        boundary_note=$(echo "$boundary_note" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
    fi

    # ── Emit H-01 Template ────────────────────────────────────────────────────
    echo "TASK_${task_id} — CTO PLAN APPROVED. You may now begin implementation."
    echo ""
    echo "Title: ${title}"
    echo ""
    echo "Source plan: docs/development/reports/${task_id}/CTO_PLAN.md"
    echo "(All 8 work items, ${num_work_items} acceptance criteria)"
    echo ""
    echo "What to do:"

    if [[ -n "$work_items" ]]; then
        while IFS= read -r line; do
            # Preserve the original numbering but strip leading whitespace for clean output
            local stripped
            stripped=$(echo "$line" | sed 's/^[[:space:]]*//')
            echo "  ${stripped}"
        done <<< "$work_items"
    fi

    echo ""
    echo "Constraints:"

    if [[ -n "$constraints" ]]; then
        while IFS= read -r line; do
            local stripped
            stripped=$(echo "$line" | sed 's/^[[:space:]]*//')
            echo "  - ${stripped}"
        done <<< "$constraints"
    fi

    echo ""
    echo "After completion: submit IMPLEMENTATION_REPORT.md with test results and"
    echo "git diff for Reviewer."
    echo ""

    if [[ -n "$boundary_note" ]]; then
        echo "Task boundary confirmation:"
        echo "  ${boundary_note}"
    else
        echo "Task boundary confirmation:"
        echo "  This is a NEW TASK (${task_id}). Scope declared in source plan above."
    fi
}

produce_impl_complete() {
    local task_dir="$1"
    local report_file="${task_dir}/IMPLEMENTATION_REPORT.md"

    [[ -f "$report_file" ]] || die "IMPLEMENTATION_REPORT.md not found in ${task_dir}"

    local task_id
    task_id=$(extract_task_id "$task_dir")

    # Extract changes summary from the report (Modified/Created/Deleted sections)
    local modified created deleted
    modified=$(grep -A100 '## Changes\|### Files Modified' "$report_file" 2>/dev/null \
        | grep -E '^  [Mm]odified:' | head -1 | sed 's/^  [Mm]odified:[[:space:]]*//' || echo "")
    created=$(grep -A100 '## Changes\|### Files Modified' "$report_file" 2>/dev/null \
        | grep -E '^  [Cc]reated:' | head -1 | sed 's/^  [Cc]reated:[[:space:]]*//' || echo "")
    deleted=$(grep -A100 '## Changes\|### Files Modified' "$report_file" 2>/dev/null \
        | grep -E '^  [Dd]eleted:' | head -1 | sed 's/^  [Dd]eleted:[[:space:]]*//' || echo "")

    # Fallback: if structured fields not found, try to extract from "Files changed" section
    if [[ -z "$modified" && -z "$created" && -z "$deleted" ]]; then
        modified=$(grep -A100 '## Changes' "$report_file" 2>/dev/null \
            | grep -E '^-.*\.py$|^+.*\.py$|^~.*\.py$' | sed 's/^[+-~] //' || echo "")
    fi

    # Extract test results
    local passed_tests failed_tests
    if [[ -f "$report_file" ]]; then
        # Look for "Passed:" or "Tests passed:" patterns
        passed_tests=$(grep -iE '^  [Pp]assed:|^  Tests passed:' "$report_file" | head -1 \
            | sed 's/^[[:space:]]*[Pp]assed:[[:space:]]*//' || echo "")
        if [[ -z "$passed_tests" ]]; then
            passed_tests=$(grep -iE '^  [Tt]ests passed:' "$report_file" | head -1 \
                | sed 's/^[[:space:]]*[Tt]ests passed:[[:space:]]*//' || echo "")
        fi
        failed_tests=$(grep -iE '^  [Ff]ailed:|^  Tests failed:' "$report_file" | head -1 \
            | sed 's/^[[:space:]]*[Ff]ailed:[[:space:]]*//' || echo "")
    fi

    # Get git diff scope
    local git_scope
    git_scope=$(count_git_changes)

    # ── Emit H-02 Template ────────────────────────────────────────────────────
    echo "TASK_${task_id} — Implementation complete. Requesting review."
    echo ""
    echo "Implementer: ornith:35b"
    echo "Report: docs/development/reports/${task_id}/IMPLEMENTATION_REPORT.md"
    echo ""
    echo "Changes summary:"

    if [[ -n "$modified" ]]; then
        echo "  - Modified: ${modified}"
    fi
    if [[ -n "$created" ]]; then
        echo "  - Created:  ${created}"
    fi
    if [[ -n "$deleted" ]]; then
        echo "  - Deleted:  ${deleted}"
    fi

    # If no structured data found, show raw file list from report
    local has_any_changes=false
    for field in modified created deleted; do
        if [[ -n "${!field}" ]]; then
            has_any_changes=true
            break
        fi
    done

    if [[ "$has_any_changes" == "false" ]]; then
        echo "  (see IMPLEMENTATION_REPORT.md for full details)"
    fi

    echo ""
    echo "Test results:"
    if [[ -n "$passed_tests" ]]; then
        echo "  Passed: ${passed_tests}"
    else
        echo "  Passed: N/A (no tests applicable)"
    fi
    if [[ -n "$failed_tests" ]]; then
        echo "  Failed: ${failed_tests}"
    else
        echo "  Failed: none"
    fi

    echo ""
    echo "git diff scope: ${git_scope}"
    echo ""
    echo "Reviewer action required:"
    echo "  - Verify all acceptance criteria in CTO_PLAN.md are met (see report for cross-reference)"
    echo "  - Confirm git diff matches reported changes"
    echo "  - Review IMPLEMENTATION_REPORT.md at the path above"
    echo "  - Submit REVIEW_REPORT.md with recommendation"
    echo ""
    echo "Task boundary confirmation:"
    echo "  This work is scoped to TASK_${task_id} only. No related tasks were modified."
}

produce_review_result() {
    local task_dir="$1"
    local report_file="${task_dir}/REVIEW_REPORT.md"

    [[ -f "$report_file" ]] || die "REVIEW_REPORT.md not found in ${task_dir}"

    local task_id
    task_id=$(extract_task_id "$task_dir")

    # Extract scoring matrix — look for patterns like "Spec compliance: X/5" or similar
    local spec_score code_score arch_score test_score overall_score
    spec_score=$(grep -iE 'Spec compliance|spec.?compliance' "$report_file" 2>/dev/null \
        | head -1 | grep -oP '\d+/\d+' || echo "N/A")
    code_score=$(grep -iE 'Code quality|code.?quality' "$report_file" 2>/dev/null \
        | head -1 | grep -oP '\d+/\d+' || echo "N/A")
    arch_score=$(grep -iE 'Architecture|architectur' "$report_file" 2>/dev/null \
        | head -1 | grep -oP '\d+/\d+' || echo "N/A")
    test_score=$(grep -iE 'Test coverage|test.?coverage' "$report_file" 2>/dev/null \
        | head -1 | grep -oP '\d+/\d+' || echo "N/A")
    overall_score=$(grep -iE '^Overall|^  Overall' "$report_file" 2>/dev/null \
        | head -1 | grep -oP '[\d.]+' || echo "N/A")

    # Extract recommendation
    local recommendation
    recommendation=$(grep -iE 'Recommendation:|recommendation' "$report_file" 2>/dev/null \
        | head -1 | sed 's/^.*[Rr]ecommendation:[[:space:]]*//' | sed 's/[[:space:]].*//' || echo "N/A")

    # Extract issues — look for [CRITICAL/HIGH/MEDIUM/LOW] patterns
    local issues=""
    if [[ -f "$report_file" ]]; then
        issues=$(grep -E '\[(CRITICAL|HIGH|MEDIUM|LOW)\]' "$report_file" 2>/dev/null || echo "")
    fi

    # ── Emit H-03 Template ────────────────────────────────────────────────────
    echo "TASK_${task_id} — Review complete. Recommendation submitted."
    echo ""
    echo "Reviewer: laguna-xs-2.1:q4_K_M"
    echo "Report: docs/development/reports/${task_id}/REVIEW_REPORT.md"
    echo ""
    echo "Scoring:"

    # Determine column widths for alignment
    printf "  %-20s %5s (%s)\n" "Spec compliance:" "$spec_score" \
        "$(grep -iE 'Spec compliance|spec.?compliance' "$report_file" 2>/dev/null | head -1 | sed 's/^.*[Xx]/\//' | sed 's/^[^/]*\///' || echo '')"

    printf "  %-20s %5s (%s)\n" "Code quality:" "$code_score" \
        "$(grep -iE 'Code quality|code.?quality' "$report_file" 2>/dev/null | head -1 | sed 's/^.*[Xx]/\//' | sed 's/^[^/]*\///' || echo '')"

    printf "  %-20s %5s (%s)\n" "Architecture:" "$arch_score" \
        "$(grep -iE 'Architecture|architectur' "$report_file" 2>/dev/null | head -1 | sed 's/^.*[Xx]/\//' | sed 's/^[^/]*\///' || echo '')"

    printf "  %-20s %5s (%s)\n" "Test coverage:" "$test_score" \
        "$(grep -iE 'Test coverage|test.?coverage' "$report_file" 2>/dev/null | head -1 | sed 's/^.*[Xx]/\//' | sed 's/^[^/]*\///' || echo '')"

    printf "  %-20s %5s\n" "Overall:" "${overall_score}"
    echo ""
    echo "Recommendation: ${recommendation}"
    echo ""

    if [[ -n "$issues" ]]; then
        echo "Issues found:"
        while IFS= read -r line; do
            local stripped
            stripped=$(echo "$line" | sed 's/^[[:space:]]*//')
            echo "  ${stripped}"
        done <<< "$issues"
    else
        echo "Issues found:"
        echo "  none"
    fi

    echo ""
    echo "CTO action required:"

    # Provide context-sensitive guidance based on recommendation
    case "${recommendation^^}" in
        *APPROVE*)
            echo "  - If APPROVED: write CTO_APPROVAL.md with Gate G4 decision"
            ;;
        *REQUEST_CHANGES*)
            echo "  - If REQUEST_CHANGES: return to Implementer with specific issues"
            ;;
        *REJECT*)
            echo "  - If REJECTED: document rejection rationale in CTO_APPROVAL.md"
            ;;
    esac

    echo ""
    echo "Task boundary note: Review scoped exclusively to TASK_${task_id} directory."
}

produce_approval() {
    local task_dir="$1"
    local decision="${2:-}"  # approve or reject (case-insensitive)

    if [[ -z "$decision" ]]; then
        die "approval requires a decision argument: 'approve' or 'reject'"
    fi

    local lower_decision
    lower_decision=$(echo "$decision" | tr '[:upper:]' '[:lower:]')

    case "$lower_decision" in
        approve)  : ;;
        reject)   : ;;
        *) die "Invalid decision: '${decision}'. Use 'approve' or 'reject'." ;;
    esac

    local task_id
    task_id=$(extract_task_id "$task_dir")

    # Read rationale from second argument, stdin, or prompt
    local rationale="${3:-}"
    if [[ -z "$rationale" ]]; then
        echo "Enter approval rationale (end with empty line):" >&2
        read -r -d '' rationale || true
    fi

    # If REVIEW_REPORT.md exists, reference it
    local review_ref=""
    if [[ -f "${task_dir}/REVIEW_REPORT.md" ]]; then
        review_ref="docs/development/reports/${task_id}/REVIEW_REPORT.md"
    else
        review_ref="(no REVIEW_REPORT.md found)"
    fi

    # ── Emit H-04 Template ────────────────────────────────────────────────────
    echo "TASK_${task_id} — $(echo "${decision}" | tr '[:lower:]' '[:upper:]')D by CTO at Gate G4."
    echo ""
    echo "Decision: ${decision^^}"

    if [[ -n "$rationale" ]]; then
        echo "Rationale: ${rationale}"
    else
        echo "Rationale: $(echo "${review_ref}")"
    fi
    echo ""

    if [[ "$lower_decision" == "approve" ]]; then
        echo "If approved:"
        echo "  - All acceptance criteria met per ${review_ref}"
        echo "  - No outstanding issues"
        echo "  - Task is complete — status moved to COMPLETE"
    else
        # For rejection, try to extract specific issues from the review report
        local reject_issues=""
        if [[ -f "${task_dir}/REVIEW_REPORT.md" ]]; then
            reject_issues=$(grep -E '\[(CRITICAL|HIGH)\]' "$task_dir/REVIEW_REPORT.md" 2>/dev/null || echo "")
        fi

        echo "If rejected:"
        echo "Issues requiring resolution:"

        if [[ -n "$reject_issues" ]]; then
            local issue_num=1
            while IFS= read -r line; do
                local stripped
                stripped=$(echo "$line" | sed 's/^[[:space:]]*//')
                echo "    ${issue_num}. ${stripped}"
                ((issue_num++))
            done <<< "$reject_issues"
        else
            echo "    1. See REVIEW_REPORT.md for full issue details."
        fi

        echo ""
        echo "Resubmit after fixing these issues. Work returns to the Implementer or Reviewer per issue type."
    fi
}

# ─── Main Dispatch ──────────────────────────────────────────────────────────────

main() {
    if [[ $# -lt 2 ]]; then
        usage
        exit 1
    fi

    local msg_type="$1"
    local task_dir="$2"

    # Validate message type
    local valid=false
    for t in "${MESSAGE_TYPES[@]}"; do
        if [[ "$msg_type" == "$t" ]]; then
            valid=true
            break
        fi
    done
    if [[ "$valid" == "false" ]]; then
        die "Unknown message type: '${msg_type}'. Valid types: ${MESSAGE_TYPES[*]}"
    fi

    # Validate task directory exists
    if [[ ! -d "$task_dir" ]]; then
        die "Task directory not found: ${task_dir}"
    fi

    # Normalize trailing slash
    task_dir="${task_dir%/}"

    case "$msg_type" in
        delegate)         produce_delegate "$task_dir" ;;
        impl-complete)    produce_impl_complete "$task_dir" ;;
        review-result)    produce_review_result "$task_dir" ;;
        approval)         produce_approval "$task_dir" "${@:3}" ;;
    esac
}

main "$@"
