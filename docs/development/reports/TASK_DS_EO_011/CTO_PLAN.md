# CTO Plan — TASK_DS_EO_011

**Task**: TASK_DS_EO_011  
**agent_id**: cto  
**session_id**: _(filled at execution time)_  
**model**: ollama/qwen3.6:35b  
**produced_at**: 2026-07-29T08:15PDT  

---

## Objective

Define standardized, template-driven message formats for all cross-role handoff points in the DS-EO workflow, and produce a script that generates these messages automatically from artifact data. This eliminates manual message composition as a failure mode and ensures every handoff contains the same required information in the same structure.

---

## Current Problem

The communication protocol (`docs/development/protocols/communication_protocol.md`) defines **JSON schemas** for message types (field names and their expected values) but does not define:
- The human-readable text format used when the message is actually delivered to an agent
- Which fields are required vs. optional in each direction
- A reusable template or script that produces these messages

As a result, every handoff is manually composed, leading to:
1. Inconsistent structure (some include scope, some don't; some list constraints, some don't)
2. Missing required information (e.g., the Implementer was told to implement TASK_DS_EO_009 but wasn't given a structured task directory with clear deliverables)
3. Task conflation risk (no explicit "this is not X, this is Y" boundary declaration)

---

## Section 1: Handoff Message Templates

Every handoff message MUST follow one of the five templates below. No ad-hoc text substitutions for the required fields are permitted.

### Template H-01: CTO → Implementer (Task Delegation)

**When**: CTO completes planning and delegates implementation work  
**Format**:
```
TASK_<id> — CTO PLAN APPROVED. You may now begin implementation.

Title: <title from CTO_PLAN.md>

Source plan: docs/development/reports/TASK_<id>/CTO_PLAN.md
(All 8 work items, N acceptance criteria)

What to do:
  1. <work item 1 — imperative verb start>
  2. <work item 2>
  ...

Constraints:
  - <constraint 1>
  - <constraint 2>
  ...

After completion: submit IMPLEMENTATION_REPORT.md with test results and
git diff for Reviewer.

Task boundary confirmation:
  This is a NEW TASK (<id>) — NOT related to <conflicted-task-ids-if-applicable>.
```

**Required fields**: taskId, title, sourcePlan (relative path), workItems (numbered list), constraints (bulleted list), taskBoundaryNote (if applicable)

### Template H-02: Implementer → Reviewer (Implementation Complete)

**When**: Implementer finishes implementation and requests review  
**Format**:
```
TASK_<id> — Implementation complete. Requesting review.

Implementer: <agent name/model>
Report: docs/development/reports/TASK_<id>/IMPLEMENTATION_REPORT.md

Changes summary:
  - Modified: <file paths>
  - Created:  <file paths>
  - Deleted:  <file paths>

Test results:
  Passed: <test names or "N/A if no tests applicable">
  Failed: <test names with reason, or "none">

git diff scope: N file(s) changed across M dir(s)

Reviewer action required:
  - Verify all acceptance criteria in CTO_PLAN.md are met (see report for cross-reference)
  - Confirm git diff matches reported changes
  - Review IMPLEMENTATION_REPORT.md at the path above
  - Submit REVIEW_REPORT.md with recommendation

Task boundary confirmation:
  This work is scoped to TASK_<id> only. No related tasks were modified.
```

### Template H-03: Reviewer → CTO (Review Complete)

**When**: Reviewer finishes review and recommends a decision  
**Format**:
```
TASK_<id> — Review complete. Recommendation submitted.

Reviewer: <agent name/model>
Report: docs/development/reports/TASK_DS_EO_011/REVIEW_REPORT.md

Scoring:
  Spec compliance:   X/5 (<details>)
  Code quality:      X/5 (<details>)
  Architecture:      X/5 (<details>)
  Test coverage:     X/5 (<details>)
  Overall:           X.X (weighted average)

Recommendation: <APPROVE | APPROVE_WITH_COMMENTS | REQUEST_CHANGES | REJECT>

Issues found:
  [CRITICAL/HIGH/MEDIUM/LOW] <description> — <location if applicable>

CTO action required:
  - If APPROVED: write CTO_APPROVAL.md with Gate G4 decision
  - If REQUEST_CHANGES: return to Implementer with specific issues
  - If REJECT: document rejection rationale in CTO_APPROVAL.md

Task boundary note: Review scoped exclusively to TASK_<id> directory.
```

### Template H-04: CTO → User (Approval Decision)

**When**: CTO issues final approval or rejection  
**Format**:
```
TASK_<id> — <APPROVED | REJECTED> by CTO at Gate G4.

Decision: <APPROVE | REJECT>
Rationale: <one-paragraph summary referencing Reviewer's recommendation and spec compliance>

If approved:
  - All acceptance criteria met per REVIEW_REPORT.md
  - No outstanding issues
  - Task is complete — status moved to COMPLETE

If rejected:
  Issues requiring resolution:
    1. <issue description with reference to specific artifact/section>
    2. ...
  
  Resubmit after fixing these issues. Work returns to the Implementer or Reviewer per issue type.
```

### Template H-05: CTO → User / Agent (Task Status Update)

**When**: Any agent reports progress, stall, or status change during a task  
**Format**:
```
TASK_<id> — STATUS: <IN_PROGRESS | BLOCKED | AWAITING_REVIEW | COMPLETE | REJECTED>

<brief description of what happened and why the status changed>

If BLOCKED: blocker = <description>; blocking agent = <role or "User">; expected resolution = <who/how/when>
If COMPLETE: final deliverable(s) = <file paths>
```

---

## Section 2: Handoff Message Generation Script

Create `/home/deepsim/ds-eo-openclaw/scripts/generate_handoff_message.sh` that reads task artifacts and outputs the formatted message for each handoff type.

**Usage**:
```bash
# CTO → Implementer (delegation)
generate_handoff_message.sh delegate <task_dir>

# Implementer → Reviewer (completion)
generate_handoff_message.sh impl-complete <task_dir>

# Reviewer → CTO (review result)
generate_handoff_message.sh review-result <task_dir>

# CTO → User (approval decision)
generate_handoff_message.sh approval <task_dir>
```

**Input sources per type**:

| Message Type | Reads From | Produces To |
|-------------|-----------|------------|
| delegate | `CTO_PLAN.md` (work items, constraints, title) | stdout |
| impl-complete | `IMPLEMENTATION_REPORT.md` + `git diff --stat` | stdout |
| review-result | `REVIEW_REPORT.md` (scores, recommendation, issues) | stdout |
| approval | CTO decision input (manual: approve/reject + rationale) | stdout |

**Script design**:

```bash
#!/usr/bin/env bash
# generate_handoff_message.sh — Produce standardized handoff messages
# Usage: generate_handoff_message.sh <message-type> <task-dir> [additional-args...]

set -euo pipefail

MESSAGE_TYPES=(delegate impl-complete review-result approval)

usage() {
    echo "Usage: $0 <delegate|impl-complete|review-result|approval> <task-dir>"
    for t in "${MESSAGE_TYPES[@]}"; do echo "  $t — $(echo "$t" | sed 's/-complete/ completion/g')"; done
}

# Delegate: read CTO_PLAN.md work items and constraints, emit H-01 template
produce_delegate() {
    local task_dir="$1"
    # Extract work items (numbered list under "What to do:")
    # Extract constraints (bulleted list under "Constraints:")
    # Read title from file header
    # Emit formatted H-01
}

# Impl-complete: read IMPLEMENTATION_REPORT.md + git diff, emit H-02 template  
produce_impl_complete() {
    local task_dir="$1"
    # Extract changes summary
    # Run git diff --stat in the repo root for scope
    # Emit formatted H-02
}

# Review-result: read REVIEW_REPORT.md scores, emit H-03 template
produce_review_result() {
    local task_dir="$1"
    # Parse scoring matrix from REVIEW_REPORT.md
    # Extract recommendation and issues
    # Emit formatted H-03
}

# Approval: accepts decision + rationale from stdin or args
produce_approval() {
    local task_dir="$1"
    local decision="${2:-}"  # approve or reject
    # Read review report for compliance reference
    # Emit formatted H-04
}
```

---

## Section 3: Communication Protocol Update

Update `ds-eo-openclaw/docs/development/protocols/communication_protocol.md` with the following additions:

### New section after existing Message Types (after §9):

```markdown
## Handoff Message Templates

All handoff messages MUST follow one of these templates. Ad-hoc message composition is prohibited.

(Insert templates H-01 through H-05 here)
```

### Update Rule 2 in Communication Rules:

**Old**: "Messages should be concise; detailed content goes into artifact files, not chat messages."  
**New**: "Messages MUST use the standardized handoff message templates (H-01 through H-05). Detailed content goes into artifact files; the handoff message is a structured summary that links to them. Use `scripts/generate_handoff_message.sh` for automated generation when artifacts are present."

### Add:

**Rule 6**: "Every cross-role handoff (CTO→Implementer, Implementer→Reviewer, Reviewer→CTO) MUST include a task boundary confirmation if there is any risk of conflation with other tasks. Use the format `Task boundary note:` followed by explicit scope declaration."

### Add:

**Section — Automation**: "Handoff messages can be generated automatically via `scripts/generate_handoff_message.sh`. When this script exists and succeeds, it should be used as the primary mechanism for producing handoff messages. Manual override is allowed only when artifact data is incomplete and the CTO determines a manual message is necessary."

---

## Section 4: Template Updates to Artifact Files

Update templates in `ds-eo-openclaw/templates/` to include a "Handoff Message" section that indicates what message type will be generated and where.

### In `report_template.md` (IMPLEMENTATION_REPORT):
Add at the end, after Known Limitations:
```markdown
## Handoff Message

Use `scripts/generate_handoff_message.sh impl-complete <task-dir>` to produce the standard
completion message for this task, or compose a manual H-02 template.
```

### In `review_report_template.md`:
Add at the end:
```markdown
## Handoff Message

After writing this report, use `scripts/generate_handoff_message.sh review-result <task-dir>` 
to produce the standard review completion message for CTO review.
```

---

## Acceptance Criteria

| # | Criterion | Weight |
|---|-----------|--------|
| A1 | All 5 handoff templates (H-01 to H-05) defined with required fields | 15% |
| A2 | `generate_handoff_message.sh` script created and tested against valid TASK_DS_EO_010 artifacts | 20% |
| A3 | communication_protocol.md updated with templates section, rules, and automation section | 15% |
| A4 | Templates updated (report_template.md, review_report_template.md) to reference the script | 10% |
| A5 | Script tested: produces valid output for each of the 4 executable message types against TASK_DS_EO_010 | 20% |
| A6 | Task boundary note format defined and included in H-01 template (and all templates that could benefit from it) | 10% |
| A7 | All changes committed to repository with a clean working tree | 10% |

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Templates are too rigid for edge cases | Medium | H-05 (status update) intentionally flexible; manual override permitted when script fails per protocol rule |
| Script complexity grows as new message types are added | Low | Each message type is a separate function; no cross-dependencies |
| Implementer/Reviewer ignore the script and compose manually | Low | Review phase (Criterion A5) validates that the generated message was produced or manual was justified with documented reason |

---

## Constraints

1. Do not modify any existing JSON schemas in communication_protocol.md — only ADD the templates section. The existing schemas are the machine layer; these templates are the human/agent layer.
2. Do not create runtime integration (e.g., OpenClaw hooks). This is a protocol + script deliverable only.
3. Do not touch `~/.openclaw/openclaw.json` or any gateway config files.

---

## Deliverables

1. 5 handoff message templates (H-01 through H-05)
2. `scripts/generate_handoff_message.sh` (tested, working)
3. Updated `communication_protocol.md` with new sections and rules
4. Updated template files referencing the script
5. Clean commit + documentation in this task directory

---

*Planned by: CTO Agent (ollama/qwen3.6:35b)*  
*Gate: G1 — Plan Approval Pending User Review*
