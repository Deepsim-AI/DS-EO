# DS-EO Approval Protocol (Global Standard)

**Version**: 1.0  
**Status**: Active  
**Scope**: All OpenClaw workspaces using DS-EO  

---

## Purpose

Defines formal approval gate rules, decision criteria, rejection handling, and escalation paths for the four-phase development workflow. Expands the G1–G4 gates into executable rules.

---

## Approval Gates Overview

| Gate | From → To | Authority | Decision Type |
|------|-----------|-----------|---------------|
| G1 | Phase 1 → Phase 2 | User (CTO proposes) | Approve plan / Request revision |
| G2 | Phase 2 → Phase 3 | Implementer (self-declare) + CTO confirms | Implementation complete? |
| G3 | Phase 3 → Phase 4 | Reviewer (recommendation) | Review passes? |
| G4 | Phase 4 → Complete | CTO (final decision) | Approve or reject implementation |

---

## Gate Definitions

### Gate G1: User Approval of Task Plan

**Authority**: User  
**Triggered by**: CTO submitting `CTO_PLAN.md` for review  

**Decision criteria**:
- Acceptance criteria are clear, testable, and derived from the spec
- Proposed changes are scoped appropriately (no unauthorized scope expansion)
- Implementation plan is feasible and well-ordered
- Risks are identified with mitigations

**Outcomes**:
| Outcome | Action |
|---------|--------|
| Approved | Proceed to Phase 2. CTO delegates to Implementer. |
| Request revision | CTO revises plan addressing user concerns; resubmit to G1 |

---

### Gate G2: Implementation Complete

**Authority**: Implementer (self-declares) → CTO (confirms artifacts exist)
**Triggered by**: Implementer submitting `IMPL_COMPLETE` message

**Decision criteria**:
- All items on the **G2 Gate Checklist** (see unified checklist below) are verified complete
- Code changes applied per CTO_PLAN.md scope
- No unresolved blockers or ambiguities left unflagged

**Outcomes**:
| Outcome | Action |
|---------|--------|
| Confirmed complete | Proceed to Phase 3. CTO forwards task to Reviewer. |
| Incomplete | Return to Implementer with specific gaps identified |

---

### Gate G3: Review Passes

**Authority**: Development Reviewer (recommends) → CTO (confirms)
**Triggered by**: Reviewer submitting review findings via `REVIEW_COMPLETE` message and writing REVIEW_REPORT.md to task directory

**Prerequisites (verified by CTO before accepting handoff)**:
- All Phase 2 and Phase 3 artifacts carry required metadata fields (`agent_id`, `session_id`, `model`, `produced_at`)

**Decision criteria**:
- Review report exists with all required sections
- Spec compliance matrix completed
- Regression analysis performed
- Scoring rubric applied with justification
- Recommendation is clear and threshold-compliant

**Outcomes**:
| Outcome | Action |
|---------|--------|
| APPROVE / APPROVE_WITH_COMMENTS | Proceed to Phase 4. CTO reviews findings and makes final decision. |
| REQUEST_CHANGES / REJECT | Return to Implementer with specific issues from Reviewer's report (REVIEW_REPORT.md). Implementer fixes and resubmits (loop back to Phase 3). |

---

### Gate G4: Final Approval

**Authority**: CTO
**Triggered by**: CTO reviewing Reviewer's report + Implementer's implementation report

**Decision criteria**:
- Reviewer's recommendation is considered alongside CTO's own assessment
- All acceptance criteria from `CTO_PLAN.md` are met in the implementation
- No unresolved architecture concerns
- Documentation updated to reflect changes (if required by workflow)
- **All artifacts in task directory verified for required metadata fields**
- **Tool-policy compliance verified**: no agent was asked to produce something its tool policy blocks

**Outcomes**:
| Outcome | Action |
|---------|--------|
| APPROVE | Write `CTO_APPROVAL.md`. Move spec to completed. Communicate to user. Task complete. |
| REJECT | Write `CTO_APPROVAL.md` with rejection rationale. Return to Implementer or Reviewer based on issue type. |

---

## Rejection Handling Procedures

### When Phase 1 is Rejected by User (G1)

1. CTO documents user's concerns in revised plan
2. CTO resubmits `CTO_PLAN.md` with changes highlighted
3. Returns to G1 for re-approval

### When Implementer is Returned from Phase 3 (G3 — REQUEST_CHANGES/REJECT by Reviewer)

1. CTO reviews Reviewer's report and identifies root cause:
   - **Spec non-compliance** → Return to Implementer with specific requirements to address
   - **Code quality issue** → Return to Implementer with quality standards reference
   - **Architecture deviation** → May require architecture change proposal from CTO first
2. Implementer addresses issues and resubmits (loop back to Phase 3)
3. Loop limit: If same issue returns 3+ times, escalate to user for resolution

### When CTO Rejects at Final Approval (G4)

1. CTO documents specific rejection reasons in `CTO_APPROVAL.md`
2. **Post-Rejection Artifact Cleanup**:
   - CTO notes which artifacts should be kept vs. marked stale in its rejection rationale
   - PM flags stale artifacts for review but does NOT delete them (deletion is irreversible)
   - If the Implementer resubmits, only current-cycle artifacts are evaluated
3. Decision on who receives the return:
   - **Implementation gaps** → Return to Implementer with detailed fix list
   - **Review quality issues** → Return to Reviewer for deeper analysis
4. New implementation cycle begins (loop back to Phase 2)

### Auto-Reject Rule: Off-Path Writes

If any agent writes to a file outside its designated artifact paths during a task, this is an automatic REJECT at Gate G4:
- The responsible agent reports the unauthorized write as a BLOCKER
- CTO investigates the root cause before allowing resubmission

---

## Escalation Paths

When an agent encounters ambiguity or a decision that exceeds their authority:

| Situation | Escalate To | Resolution Path |
|-----------|-------------|-----------------|
| Ambiguous spec requirement | CTO → User if needed | CTO clarifies; may require spec update |
| Architecture conflict with plan | CTO (formal proposal) | CTO proposes change; user approves; Implementer proceeds |
| Reviewer and Implementer disagree on compliance | CTO (final arbiter) | CTO makes binding decision referencing spec |
| Repeated returns (>3 cycles) | User | Break deadlock with direct user input |
---

## Gate Re-entry Rule

G1 (Planning Approval) and G2 (Implementation Completion) are normally executed **once per task**. The gate model does not support "re-opening" completed gates when subsequent phases find issues.

### Correct flow on Reviewer return (G3 → REQUEST_CHANGES):

1. Reviewer returns task to Implementer with specific findings
2. Implementer addresses the findings and re-submits
3. Task **re-enters G3** (Review) — not G2 or G1
4. G3 may iterate multiple times until Reviewer issues PASS
5. Only after G3 PASS does the task proceed to G4 for final CTO approval

### Correct flow on CTO rejection at G4:

1. CTO returns task with specific rejection reasons
2. If implementation gaps → return to Implementer (loop back to Phase 2, re-verify G2)
3. If review quality issues → return to Reviewer for deeper analysis (loop back to G3)

### Required message format on G3 return from Implementer:

When the Implementer re-submits after addressing Reviewer findings, the completion message must use this exact phrasing:

```
**G3 RE-SUBMISSION** — Task: <taskId>

All review findings have been addressed. The implementation and IMPLEMENTATION_REPORT.md have been updated. Requesting G3 re-review by the Reviewer.

Findings addressed:
- <finding 1>: <how it was addressed>
- <finding 2>: <how it was addressed>
```

**Never say "Gate G2 re-verification"** — G2 has already passed for this task. The return path from G3 does not reopen any previous gate.

### Gate State Transition Diagram:

```
G1 (Planning) → G2 (Implementation Complete) → G3 (Review)
                                                         │
                                                  PASS → G4 (Final Approval)
                                                  │
                                          REQUEST_CHANGES → Implementer fixes → G3 (re-enter)
                                                                                         │
                                                                                  [loop back to top of arrow]
```

---

## Approval Decision Template

When issuing an approval or rejection, use this structure:

```markdown
# <APPROVAL_DECISION | REJECTION> — Task: <taskId>

**Date**: YYYY-MM-DD  
**Reviewing Agent**: CTO  

**Summary**: [One sentence decision]

**Basis for Decision**:
- Reviewer's recommendation: <recommendation> (see REVIEW_REPORT.md)
- Spec compliance: <assessment>
- Code quality: <assessment>
- Architecture adherence: <assessment>

**If Approved**:
- All acceptance criteria met
- No outstanding issues

**If Rejected**:
- Issue 1: <description and required fix>
- Issue 2: <description and required fix>
- ...

**Next Steps**: [What happens next]
```

---

## Rules

1. Only the CTO may issue final approval or rejection (Gate G4).
2. The User is the sole authority for Gate G1 (plan approval).
3. All decisions must reference specific evidence — no vague approvals or rejections.
4. Rejection must include actionable feedback, not just a negative decision.
5. Escalation paths are mandatory when an agent cannot resolve ambiguity within their scope.

---

## G2 Gate Checklist (Unified)

This checklist is the authoritative source for Gate G2 prerequisites. Both `completion_protocol.md` and `handoff_protocol.md` reference this list — do not define parallel variants.

- [ ] Code changes applied per CTO_PLAN.md scope
- [ ] All existing tests still passing (no regressions)
- [ ] IMPLEMENTATION_REPORT.md exists with:
  - [ ] Files changed summary
  - [ ] Design decisions and rationale
  - [ ] Test results (pass/fail for each)
  - [ ] Known limitations
  - [ ] Reference to acceptance criteria
- [ ] No unresolved TODOs/FIXMEs that block verification
- [ ] Artifacts carry required metadata (agent_id, produced_at)

---

## Related Protocols

- `communication_protocol.md` — Message format standards (APPROVAL_DECISION)
- `completion_protocol.md` — CTO completion checklist; references G2 Gate Checklist above
- `handoff_protocol.md` — Phase 4 → Complete transition
