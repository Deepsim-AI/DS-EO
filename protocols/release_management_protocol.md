# DS-EO Release Management Protocol (PM)

**Version**: 1.0  
**Status**: Active  
**Scope**: PM role — task closure, documentation sync, repository lifecycle coordination, release state  

---

## Purpose

Defines how the Project Manager manages task closure, documentation synchronization verification, repository lifecycle coordination, and release state. This protocol replaces the former `status_protocol.md` and consolidates all post-implementation lifecycle management under a single document.

---

## Scope

- Task closure procedures (post-G4)
- Documentation synchronization verification
- Repository lifecycle coordination — stage-by-stage split between PM/CTO/Implementer; PM coordinates and verifies but **never executes Git/GitHub operations**
- Release notes / checklist assembly
- Milestone tracking conventions
- Local vs. remote repository handling

---

## PM Authority

| Power | Description |
|-------|-------------|
| Stall a task | Can flag a task as **STALLED** when no progress is detected for 24+ hours |
| Demand update | Can require an agent to provide a status update within 12 hours of the stall notice |
| Coordinate lifecycle | Coordinates all repository lifecycle stages (planning, verifying, approving) but does not execute Git/GitHub operations |
| Assemble release notes | Compiles CHANGELOG entries from completed task reports |

**Cannot override**: CTO's architectural decisions or Reviewer's quality verdicts.

---

## Boundary with CTO

- **PM tracks WHAT was done.** CTO decides WHAT should be built.
- PM updates `PROJECT_STATUS.md` from completed task reports; CTO updates `ROADMAP.md`.
- PM coordinates repository state transitions; CTO approves milestones and releases.
- Milestone tracking is against ROADMAP objectives (roadmap authoring remains CTO/User).

---

## Repository State Machine

PM owns transitions from **Review Passed** through **Closed**:

```
Working → Implementation Complete → Review Passed → Documentation Synchronized → Repository Synchronized → Released (optional) → Closed
```

### Transition Conditions

| From | To | Trigger |
|------|----|---------|
| Working | Implementation Complete | Implementer reports completion with all required artifacts |
| Implementation Complete | Review Passed | CTO issues Gate G4 approval |
| Review Passed | Documentation Synchronized | PM verifies documentation is current against implementation report |
| Documentation Synchronized | Repository Synchronized | PM coordinates and confirms local commit, tag (if applicable), and remote push completed successfully |
| Repository Synchronized | Released | Optional stage — CTO approves release; PM assembles release notes |
| Repository Synchronized / Released | Closed | PM closes task directory status as "COMPLETE" after all verifications pass |

---

## Task Closure Procedure (post-G4)

After the CTO issues Gate G4 approval, PM executes the following:

1. **Verify artifacts** — Confirm all required artifacts from `completion_protocol.md` exist in the task directory
2. **Update PROJECT_STATUS.md** — Mark the task as complete with date and summary
3. **Compile CHANGELOG entries** — Extract change descriptions from the implementation report
4. **Flag milestone completion** — If applicable, note which ROADMAP objective was satisfied
5. **Close task directory status** — Set task directory status to "COMPLETE"

### Closure Verification Checklist

- [ ] All artifacts present (per `completion_protocol.md` role checklists)
- [ ] No unresolved TODOs or FIXMEs in changed code (documented if unavoidable)
- [ ] Documentation reflects actual implementation
- [ ] CHANGELOG entry drafted and reviewed against task report
- [ ] Milestone impact assessed (if applicable)

---

## Repository Lifecycle Coordination (Stage-by-Stage Split)

| Stage | PM | CTO | Implementer |
|-------|----|-----|-------------|
| Verify task is complete | Owns | Reviews/approves | Provides deliverables |
| Check documentation updated | Owns | Reviews if needed | Contributes |
| Verify tests passed | Owns | Reviews | Runs tests |
| Prepare commit plan | Owns | Approves if significant | Executes/assists |
| Commit message standard | Owns | Defines policy | Follows policy |
| Local Git commit | Coordinates | Approves milestone | Usually executes |
| Tag release | Coordinates | Approves | Executes |
| Push to GitHub/remote | Coordinates after approval | Approves release/milestone | Executes |
| Close task | Owns | Final approval | — |

### Commit Message Standard

PM defines the commit message format. Conventional Commits recommended:

```
<type>(<scope>): <short summary>

[optional body with context, rationale, references]
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`  
Scope: Task ID or component name (e.g., `TASK-001`, `auth`)

---

## Documentation Synchronization Verification

PM verifies that documentation is current after implementation. The following must be checked:

### Required Checks

| Check | Source of Truth | Resolution Method |
|-------|----------------|-------------------|
| Code comments match actual behavior | Implementation report + changed files | Compare; flag discrepancies to Implementer |
| API docs reflect new endpoints/signatures | Implementation report | Confirm or request update from Implementer |
| README / changelog updated for user-facing changes | CHANGELOG entries compiled by PM | Verify against implementation scope |
| Architecture diagrams (if applicable) reflect changes | CTO_PLAN.md references | Flag to CTO if structural change documented |

### Verification Procedure

1. Read the `IMPLEMENTATION_REPORT.md` from the task directory
2. Cross-reference each "files modified/created/deleted" entry against actual repository state
3. Confirm documentation files are updated (not just code)
4. If discrepancies found, return to Implementer with specific gaps — do not proceed until resolved

---
---

## Release Workflow Dispatch (R-REL-2 Mandate)

**This section implements the mandatory release workflow dispatch requirement from TASK_DS_EO_046.**
It is a required addition to this protocol and overrides any prior behavior regarding releases.

### When Workflow Dispatch Is Required

A GitHub Actions workflow dispatch **MUST** be executed whenever a release tag (`vX.Y.Z`) is created on the remote repository. This creates the Release page entry on GitHub. Without it, the release exists in Git but has no corresponding GitHub Release page entry.

### Dispatch Procedure

1. **Confirm the tag is on the remote:**
   ```bash
   git ls-remote origin refs/tags/v<X.Y.Z>
   ```
   If no output, the tag has not been pushed — abort dispatch and report `BLOCKED: tag_missing`.

2. **Determine release type** (from CTO_PLAN.md or version bump artifact):
   - `major` — breaking changes (X in vX.Y.Z)
   - `minor` — new features, no breaks (Y in vX.Y.Z)
   - `patch` — bugfixes only (Z in vX.Y.Z)

3. **Dispatch the workflow:**
   ```bash
   gh workflow run release.yml \
     --ref main \
     --field release_type='<major|minor|patch>' \
     --field tag='v<X.Y.Z>' \
     --field changelog='<summary of changes>'
   ```

4. **Verify dispatch succeeded:**
   - Check GitHub Actions run page for the dispatched workflow
   - Confirm the run started (not queued forever)
   - If the workflow fails, report `BLOCKED: release_dispatch_failed` and do NOT close the task

5. **If `gh` CLI is unavailable or GITHUB_TOKEN is missing:**
   - Document the exact dispatch URL: `https://github.com/<org>/<repo>/actions/workflows/release.yml`
   - Document the required parameters (release_type, tag, changelog)
   - Flag status as `BLOCKED_ON_RELEASE_DISPATCH` — NOT "closed"
   - Instruct the user on how to perform the dispatch manually

### Workflow Dispatch Verification Checklist

Before declaring any release-related task complete, verify:

- [ ] Tag exists on remote (`git ls-remote origin refs/tags/v<X.Y.Z>` returns a SHA)
- [ ] Workflow was dispatched with correct `release_type` parameter
- [ ] Workflow run started (not stuck in "Queued" state for >5 minutes)
- [ ] If workflow failed: error captured and reported — task NOT closed
- [ ] If dispatch not possible: URL + parameters documented, status = `BLOCKED_ON_RELEASE_DISPATCH`

---

## Milestone Tracking

- Track progress against **ROADMAP.md** objectives (roadmap authoring remains CTO/User).
- Report progress; do not set milestones independently.
- When a task satisfies a ROADMAP objective, PM notes this in the closure summary and flags it for CTO awareness.

### Milestone Completion Report Format

```markdown
## Milestone: <Objective Title>

**Status**: Partially Complete / Complete  
**Tasks contributing to milestone**: [list of completed task IDs]  
**Remaining tasks (if partial)**: [list or "none"]  
**Estimated completion**: [date or "on track for next cycle"]
```

---

## Local vs. Remote Repository Handling

| Operation | Local Repo | Remote (GitHub) |
|-----------|-----------|-----------------|
| Commit | Coordinate (Implementer usually executes) | — |
| Tag release | Coordinate (after CTO approval) | — |
| Push to remote | — | Coordinate after approval (Implementer executes) |

### Rules

1. **Never force-push** on shared branches.
2. Tags are created only with explicit CTO approval for a milestone or release.
3. Remote push requires: documentation verified → local commit confirmed → CTO approval obtained.
4. PM records the remote state (branch, tag, commit hash) in `PROJECT_STATUS.md` upon task closure.

---

## Related Protocols

- `completion_protocol.md` — Role-specific completion checklists and quality gates
- `review_protocol.md` — Review criteria and scoring rubric
- `communication_protocol.md` — Message format standards
- `handoff_protocol.md` — Phase transition requirements
