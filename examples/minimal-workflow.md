# Minimal Workflow Example — From Request to Delivery

This walkthrough demonstrates a complete task cycle using DS-EO on OpenClaw. It shows what happens at each phase and gate, including the Project Manager's lifecycle coordination role.

---

## Scenario

A user requests: "Add input validation to the configuration parser."

### Workflow Overview

```
User → PM → CTO (Plan, G1) → Implementer (G2) → Reviewer (G3) → CTO Approve (G4) → PM Closes
```

The Project Manager coordinates task lifecycle throughout — creating tasks, sending status messages, and closing after approval. The CTO owns all technical decisions.

---

## Phase 1: Planning (CTO)

### User sends request to PM

```
User → PM Agent:
"Please add input validation to the configuration parser in config/parse.py.
 The parser currently accepts any string without checking format or length.
 I need it to validate that inputs are non-empty strings ≤256 characters,
 and that numeric fields parse as valid integers."
```

### PM creates task lifecycle and delegates to CTO

The PM:
1. Creates a new task skeleton in the project tracker
2. Sends `TASK_OPEN` message (see `communication_protocol.md`) to CTO with user request
3. Monitors status — does not make technical decisions

### CTO creates task and writes plan

The CTO:
1. Receives TASK_OPEN from PM
2. Creates `docs/development/reports/TASK_20260728_001/` directory
3. Reads the relevant spec (or derives one from the request)
4. Analyzes existing code in `config/parse.py`
5. Writes `CTO_PLAN.md`:

```markdown
# CTO Implementation Plan — TASK_20260728_001

## Problem Statement
Configuration parser accepts invalid inputs without validation,
leading to runtime errors downstream.

## Current State
- `config/parse.py` has a `parse_config()` function that returns raw strings
- No input length checking exists
- Numeric fields are cast with `int()` but never validated before cast

## Proposed Changes
1. Add `_validate_string()` helper: checks non-empty, ≤256 chars
2. Add `_validate_int()` helper: checks format matches `-?\d+`
3. Integrate validators into `parse_config()` for all input fields
4. Add comprehensive tests in `tests/test_parse_validation.py`

## Acceptance Criteria
1. Empty strings raise ValueError with descriptive message
2. Strings >256 chars raise ValueError with length info
3. Non-integer numeric inputs raise ValueError with format example
4. All existing tests still pass (no regressions)
5. New test file covers ≥90% of validation paths

## Risks
- R1: Backward compatibility — callers may depend on unvalidated behavior
  → Mitigation: Add deprecation warning for first release, error in v2
```

### Gate G1: User Approves Plan

The CTO displays the plan with status line:
```
[TASK_20260728_001] PLANNING: Plan ready for review
Valid responses: APPROVE | REJECT | REQUEST_CHANGES(<issue>)
```

User responds: `APPROVE`

---

## Phase 2: Implementation (Implementer)

### PM sends TASK_ASSIGNED to Implementer

The PM forwards the delegation from CTO:
```
PM → Implementer Agent:
TASK_ASSIGNED — Task: TASK_20260728_001
Plan: docs/development/reports/TASK_20260728_001/CTO_PLAN.md
Status: In Progress
```

### Implementer executes the plan

1. Reads `CTO_PLAN.md`, confirms understanding of acceptance criteria
2. Modifies `config/parse.py` — adds validation helpers, integrates them
3. Creates `tests/test_parse_validation.py` with test cases for each criterion
4. Runs tests: all pass
5. Writes `IMPLEMENTATION_REPORT.md`:

```markdown
# Implementation Report — TASK_20260728_001

## Summary
Added input validation to configuration parser per CTO plan.

## Changes Made
| File | Action | Description |
|------|--------|-------------|
| config/parse.py | Modified | Added _validate_string() and _validate_int() helpers |
| tests/test_parse_validation.py | Created | 12 test cases covering validation paths |

## Acceptance Criteria Verification
| # | Criterion | Met? | Evidence |
|---|-----------|------|----------|
| 1 | Empty strings raise ValueError | Yes | Test validates empty string → ValueError raised |
| 2 | Strings >256 chars raise ValueError | Yes | Test sends 300-char string, verifies error message contains length |
| 3 | Non-integer numeric inputs rejected | Yes | Test sends "abc" for int field, verifies format example in error |
| 4 | Existing tests pass | Yes | All 23 existing tests PASS (0 regressions) |
| 5 | ≥90% validation path coverage | Yes | 12 new tests cover all validator branches |

## Test Results
- New tests: 12/12 PASS
- Existing tests: 23/23 PASS
- Total: 35/35 PASS, 0 FAIL

## Deviation Analysis
No deviations from the approved plan.
```

### Gate G2: Implementation Complete

Implementer signals completion. CTO verifies artifacts exist and confirms. PM updates task status to "In Review".

---

## Phase 3: Review (Reviewer)

### PM sends TASK_IN_REVIEW to Reviewer

The PM forwards the handoff:
```
PM → Reviewer Agent:
TASK_IN_REVIEW — Task: TASK_20260728_001
Implementer Report: docs/development/reports/TASK_20260728_001/IMPLEMENTATION_REPORT.md
Status: In Review
```

### Reviewer inspects implementation

Reviewer produces `REVIEW_REPORT.md` directly in the task directory (no CTO copy step):

1. Reads `CTO_PLAN.md` to understand what was supposed to be built
2. Runs `git diff` — compares actual changes against plan
3. Runs all tests — confirms no regressions
4. Inspects code quality — checks naming, structure, error messages
5. Applies scoring rubric:

| Dimension | Weight | Score | Evidence |
|-----------|--------|-------|----------|
| Specification Compliance | 40% | 5/5 | All 5 acceptance criteria met with evidence |
| Code Quality | 25% | 4/5 | Clean implementation; error messages could include field names |
| Architecture Adherence | 25% | 5/5 | Validation helpers follow existing pattern; no layer violations |
| Test Coverage & Regression | 10% | 5/5 | Comprehensive new tests, zero regressions |
| **Weighted Overall** | **100%** | **4.65/5** | (5×0.4) + (4×0.25) + (5×0.25) + (5×0.1) = 4.65 |

### Reviewer issues recommendation: APPROVE_WITH_COMMENTS
```
Scoring: Overall 4.65/5, no dimension below 2 → APPROVE threshold met
Comments: Error messages could include the field name for better debugging
Reviewer produces REVIEW_REPORT.md directly in task directory.
```

### Gate G3: Review Passes

PM updates task status to "Awaiting Approval". CTO confirms review report is complete and recommendation is justified.

---

## Phase 4: Final Approval (CTO)

### CTO makes final decision

The CTO reviews both reports independently:
- Spec compliance: Confirmed — all criteria met
- Code quality: Agrees with Reviewer — minor improvement possible but not blocking
- Architecture: Confirmed — no layer violations, follows existing patterns
- Two-layer boundary: Verified — only development code modified, no runtime agent changes

### CTO issues decision: APPROVE

```markdown
# APPROVAL — Task: TASK_20260728_001

**Date**: 2026-07-28
**Reviewing Agent**: CTO

**Summary**: Implementation approved. Input validation added per spec with comprehensive tests.

**Basis for Decision**:
- Reviewer's recommendation: APPROVE_WITH_COMMENTS (score 4.65/5)
- Spec compliance: All 5 acceptance criteria met
- Code quality: Clean implementation matching project patterns
- Architecture adherence: No unauthorized changes, layer boundaries preserved

**Next Steps**:
1. Update changelog with new validation feature
2. Communicate to user that task is complete
3. Archive task artifacts
```

### Gate G4: Approval Complete

CTO writes `CTO_APPROVAL.md`. PM updates task status to "Completed" and runs post-G4 verification checklist (see `completion_protocol.md` §Post-G4).

---

## Summary

| Phase | Agent | Artifact Produced | Gate | PM Action |
|-------|-------|-------------------|------|-----------|
| Planning | CTO | `CTO_PLAN.md` | G1 (User approves) | Creates task, sends TASK_OPEN to CTO |
| Implementation | Implementer | `IMPLEMENTATION_REPORT.md` | G2 (Complete verified) | Sends TASK_ASSIGNED to Implementer |
| Review | Reviewer | `REVIEW_REPORT.md` | G3 (Review passes) | Sends TASK_IN_REVIEW to Reviewer, updates status |
| Approval | CTO | `CTO_APPROVAL.md` | G4 (Final approve) | Updates status to "Completed" after approval |

**Total time**: Depends on implementation complexity. The workflow ensures quality at every step through formal gates and independent verification.

### Full Workflow Diagram

```
User Request → PM Lifecycle Coordination → CTO Plan (G1) → Implementer (G2) → Reviewer (G3) → CTO Approve (G4) → PM Post-G4 Verification
```
