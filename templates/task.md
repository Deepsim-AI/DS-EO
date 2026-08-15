# DS-EO Task Directory Template

## TASK Naming Convention

Format: `TASK_<YYYYMMDD>_<NNN>`

| Component | Description | Example |
|-----------|-------------|---------|
| `TASK_` | Prefix (fixed) | `TASK_` |
| `<YYYYMMDD>` | Date of creation | `20260728` |
| `_` | Separator | `_` |
| `<NNN>` | Sequential number, resets daily | `001`, `002`, ... |

**Assigned exclusively by the CTO.** Never create or reuse a TASK directory without CTO assignment.

---

## Directory Structure

Every task gets exactly this structure under `docs/development/reports/`:

```
TASK_<YYYYMMDD>_<NNN>/
├── TASK_REQUEST.md          # Intake artifact — verbatim user request (G0 owner produces)
├── LOCK.md                  # Session lock — prevents contention (current phase owner)
├── CTO_PLAN.md              # Architecture analysis + task plan (CTO produces)
├── IMPLEMENTATION_REPORT.md  # Changes, tests, decisions (Implementer produces)
├── REVIEW_REPORT.md          # Findings and recommendation (Reviewer → CTO copies)
└── CTO_APPROVAL.md           # Final approve/reject with rationale (CTO produces)
```

---

## Artifact Descriptions

### `CTO_PLAN.md`

Created during Phase 1 (Planning). Contains:
- Problem statement
- Current-state analysis
- Proposed changes with affected files
- Acceptance criteria (derived from spec)
- Risks and constraints
- Implementation instructions

### `IMPLEMENTATION_REPORT.md`

Created during Phase 2 (Implementation). Contains:
- Summary of all files modified/created/deleted
- Design decisions and rationale
- Test results (pass/fail with details on failures)
- Known limitations or follow-up items

### `REVIEW_REPORT.md`

Created during Phase 3 (Review). Copied by CTO from Reviewer's chat artifact. Contains:
- Spec compliance assessment with evidence
- Regression analysis results
- Scoring rubric application with justification
- Clear recommendation: APPROVE / APPROVE_WITH_COMMENTS / REQUEST_CHANGES / REJECT

### `CTO_APPROVAL.md`

Created during Phase 4 (Approval). Contains:
- Decision (APPROVE / REJECT)
- Rationale referencing both reports
- If rejected: specific issues to address and next steps

---

## Handoff Artifacts Summary

| Phase | Produces | Consumed By | Gate |
|-------|----------|-------------|------|
| Planning | `CTO_PLAN.md` | User (G1 approval) → Implementer | G1 |
| Implementation | `IMPLEMENTATION_REPORT.md` | Reviewer (G2 verification) | G2 |
| Review | `REVIEW_REPORT.md` (via CTO copy) | CTO (G3 confirmation + G4 decision) | G3, G4 |
| Approval | `CTO_APPROVAL.md` | User / Implementer (if rejected) | G4 |
