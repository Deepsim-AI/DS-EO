# CTO Approval — TASK_<YYYYMMDD>_<NNN>

**Task**: TASK_<YYYYMMDD>_<NNN>
**agent_id**: cto
**session_id**: <uuid from gateway runtime>
**model**: ollama/<cto-model-name>:<tag>
**produced_at**: <ISO-8601 timestamp>
**Decision Date**: YYYY-MM-DD  

---

## Summary

[One sentence stating the final decision and primary reason.]

---

## Rationale

### Reviewer's Recommendation

- **Recommendation**: <APPROVE / APPROVE_WITH_COMMENTS / REQUEST_CHANGES / REJECT>
- **Overall Score**: _/_5
- See: `REVIEW_REPORT.md`

### CTO Assessment

#### Spec Compliance
[CTO's own assessment of whether the implementation meets specifications.]

#### Code Quality
[CTO's independent quality judgment — does not simply defer to Reviewer.]

#### Architecture Adherence
[Does the change respect the established architecture and two-layer model? Verify development vs. runtime separation is preserved.]

### Two-Layer Boundary Verification

- [ ] Development agents (CTO, Implementer, Reviewer) did not interfere with runtime product agents
- [ ] No runtime code was modified outside task scope
- [ ] Architecture documentation updated if required by workflow

---

## If APPROVED

**All acceptance criteria met.** The implementation is complete and approved.

### Next Steps

1. Update spec status (active → completed)
2. Communicate completion to user
3. Archive task artifacts
4. Close out any open items from `IMPLEMENTATION_REPORT.md`

---

## If REJECTED

**The implementation does not meet the required standard.** Specific issues must be addressed:

### Issues Requiring Fix

| # | Issue | Required Action | Priority |
|---|-------|-----------------|----------|
| 1 | <description of issue> | <what to do about it> | High / Medium / Low |
| 2 | <description of issue> | <what to do about it> | ... |

### Return To

- [ ] **Implementer** — for implementation gaps (fix and resubmit)
- [ ] **Reviewer** — for review quality issues (deeper analysis needed)

### Next Steps After Fix

1. Implementer addresses issues listed above
2. Implementer resubmits with updated `IMPLEMENTATION_REPORT.md`
3. Workflow loops back to Phase 3 (Review) for re-review

---

## Notes

[Any additional context, acknowledgment of good work, or forward-looking observations.]
