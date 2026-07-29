# Implementation Report — TASK_<YYYYMMDD>_<NNN>

**Task**: TASK_<YYYYMMDD>_<NNN>
**agent_id**: implementer
**session_id**: <insert from `session_status` → sessionId at task completion>
**model**: ollama/<implementer-model-name>:<tag>
**produced_at**: <ISO-8601 timestamp at task completion>
**Implementer**: [Agent name/model]
**Date Completed**: YYYY-MM-DD  

[Brief description of what was implemented and why.]

---

## Changes Made

| File | Action | Description |
|------|--------|-------------|
| `<path/to/file>` | Created/Modified/Deleted | What changed and why |
| ... | ... | ... |

---

## Acceptance Criteria Verification

| # | Criterion (from CTO_PLAN.md) | Met? | Evidence / Notes |
|---|------------------------------|------|-----------------|
| 1 | <criterion text> | Yes/No | How it was verified |
| 2 | <criterion text> | Yes/No | How it was verified |
| ... | ... | ... | ... |

---

## Test Results

### New Tests Added

| Test Name | Status | Notes |
|-----------|--------|-------|
| `<test_name>` | PASS / FAIL | Brief description |

### Existing Tests (Regression)

| Test Suite | Status | Notes |
|------------|--------|-------|
| `<suite_name>` | PASS / FAIL | Any failures explained below |

**Failures**: [If any existing tests failed, explain why and whether they represent genuine regressions.]

---

## Design Decisions

1. **[Decision 1]**: Why this approach was chosen over alternatives.
2. **[Decision 2]**: Trade-offs considered and accepted.

---

## Known Limitations

- [ ] [Limitation 1 — what it is, impact, potential fix in future iteration]
- [ ] [Limitation 2]

---

## Deviation Analysis

Were there any deviations from the CTO's plan? If so:

| Deviation | Reason | Authorized By |
|-----------|--------|---------------|
| [Description of deviation] | Why it was necessary | CTO approval reference (if applicable) |

If no deviations: "No deviations from the approved plan."
