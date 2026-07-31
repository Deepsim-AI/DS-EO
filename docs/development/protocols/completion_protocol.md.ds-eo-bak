# DS-EO Completion Protocol (Global Standard)

**Version**: 1.0  
**Status**: Active  
**Scope**: All OpenClaw workspaces using DS-EO  

---

## Purpose

Defines role-specific completion checklists and quality gates for each phase of the development workflow. This protocol ensures every agent knows exactly what constitutes a complete, handoff-ready deliverable.

---

## Role: Implementer Completion Checklist

Before declaring implementation complete (Gate G2), the Implementer must have all of the following:

### Required Artifacts

- [ ] Code changes applied and committed (if applicable)
- [ ] Tests written for new functionality
- [ ] All existing tests still passing (no regressions)
- [ ] `IMPLEMENTATION_REPORT.md` written to task directory with:
  - [ ] Summary of all files modified/created/deleted
  - [ ] Design decisions and rationale
  - [ ] Test results (pass/fail with output for failures)
  - [ ] Known limitations or follow-up items
  - [ ] Reference to acceptance criteria and how each was met

### Quality Gate

- All acceptance criteria from `CTO_PLAN.md` are addressed in the report
- No unresolved TODOs or FIXMEs left behind (document if unavoidable)
- Code follows existing project conventions (see relevant coding standards)

---

## Role: Reviewer Completion Checklist

Before declaring review complete, the Development Reviewer must have all of the following:

### Required Artifacts

- [ ] `git diff` analysis against original spec
- [ ] Regression test run on existing tests
- [ ] `REVIEW_REPORT.md` with:
  - [ ] Spec compliance matrix (requirement → implementation status)
  - [ ] Code quality assessment (naming, structure, patterns)
  - [ ] Architecture adherence check
  - [ ] Regression analysis (what broke, if anything)
  - [ ] Scoring rubric completed (see `review_protocol.md`)
  - [ ] Clear recommendation: APPROVE / APPROVE_WITH_COMMENTS / REQUEST_CHANGES / REJECT

### Quality Gate

- Review is independent — reviewer does not validate their own work
- All spec requirements are checked, even if they appear trivially met
- Findings cite specific file locations and line references where possible

---

## Role: CTO Completion Checklist

Before issuing final approval (Gate G4), the CTO must have all of the following:

### Required Actions

- [ ] Received and reviewed Reviewer's report
- [ ] Verified Implementer's implementation report is complete
- [ ] Confirmed Reviewer's recommendation against own assessment
- [ ] `CTO_APPROVAL.md` written with:
  - [ ] Decision (APPROVE / REJECT)
  - [ ] Rationale referencing both reports
  - [ ] If rejected: specific issues to address and next steps

### Quality Gate

- Approval must reference the Reviewer's report by name/ID
- Rejection must include actionable feedback, not just "not approved"

---

## Post-G4: PM Completion Checklist (Project Manager)

After Gate G4 approval is issued, the Project Manager runs the following completion checklist. This phase occurs **after** the CTO's technical decision and is purely administrative.

### Artifact Verification

- [ ] `CTO_PLAN.md` exists in task directory
- [ ] `IMPLEMENTATION_REPORT.md` exists in task directory
- [ ] `REVIEW_REPORT.md` exists in task directory (copied by CTO)
- [ ] `CTO_APPROVAL.md` exists with APPROVE decision
- [ ] All spec requirements addressed per review report

### Project Status Update

- [ ] `PROJECT_STATUS.md` updated with completed work summary
- [ ] Task status changed to "completed" in project tracker
- [ ] Any dependency references updated (specs, related TASKs)

### Changelog Entry

- [ ] `CHANGELOG.md` entry added for user-facing changes:
  - [ ] Date and task ID referenced
  - [ ] Brief description of what was implemented
  - [ ] Link to CTO_APPROVAL.md or review report if relevant

### Milestone Flagging

- [ ] If task contributes to a milestone → flag in `PROJECT_STATUS.md`
- [ ] Summarize cumulative progress toward next milestone
- [ ] Notify relevant parties of milestone completion via `PM_STATUS_UPDATE` message

### Final Notification

- Send `PM_CLOSED` message (see `communication_protocol.md`) with verification summary.

---

## PM Role Boundaries

The Project Manager operates **only in the post-decision lifecycle**:

1. PM does not make gate decisions — that is the CTO's role.
2. PM does not write technical content — `CTO_PLAN.md` content is written by the CTO.
3. PM only verifies, records, and communicates process state after technical work is complete.

---

## Completion Message Format

Agents should use this format when announcing completion:

```markdown
**COMPLETION** — Task: <taskId>

**Phase**: <phase name>

**Artifacts Produced**:
- `<artifact_name>` at `<path>`

**Status**: All acceptance criteria met / Partially met (details below)

**Notes**: <any context for the next agent or user>
```

---

## Rules

1. A phase is not "complete" until all required artifacts exist in the task directory.
2. Incomplete submissions are returned to the originating agent — do not proceed to the next gate.
3. The Reviewer cannot write files; their completion is a chat artifact that the CTO copies into the task directory.
4. Completion checklists are minimum requirements — agents should exceed them when possible.
5. **PM completes administrative duties only after Gate G4 approval** — it does not participate in technical gates.

---

## Related Protocols

- `communication_protocol.md` — Message format standards
- `delegation_protocol.md` — How tasks are assigned
- `handoff_protocol.md` — What must exist before the next phase starts
