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
- All required artifacts present in task directory
- Test results documented (pass/fail with details)
- Implementation report references acceptance criteria and spec
- No unresolved blockers or ambiguities left unflagged

**Outcomes**:
| Outcome | Action |
|---------|--------|
| Confirmed complete | Proceed to Phase 3. CTO forwards task to Reviewer. |
| Incomplete | Return to Implementer with specific gaps identified |

---

### Gate G3: Review Passes

**Authority**: Development Reviewer (recommends) → CTO (confirms)  
**Triggered by**: Reviewer submitting review findings  

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
| REQUEST_CHANGES / REJECT | Return to Implementer with specific issues from Reviewer's report. Implementer fixes and resubmits (loop back to Phase 3). |

---

### Gate G4: Final Approval

**Authority**: CTO  
**Triggered by**: CTO reviewing Reviewer's report + Implementer's implementation report  

**Decision criteria**:
- Reviewer's recommendation is considered alongside CTO's own assessment
- All acceptance criteria from `CTO_PLAN.md` are met in the implementation
- No unresolved architecture concerns
- Documentation updated to reflect changes (if required by workflow)

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
2. Decision on who receives the return:
   - **Implementation gaps** → Return to Implementer with detailed fix list
   - **Review quality issues** → Return to Reviewer for deeper analysis
3. New implementation cycle begins (loop back to Phase 2)

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

## Related Protocols

- `communication_protocol.md` — Message format standards (APPROVAL_DECISION)
- `completion_protocol.md` — CTO completion checklist
- `handoff_protocol.md` — Phase 4 → Complete transition
