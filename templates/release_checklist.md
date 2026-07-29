# Release Checklist — {{VERSION}}

**Target Milestone**: {{MILESTONE_NAME}}  
**Compiled By**: PM (Project Manager) agent  
**Date**: {{DATE}}  

---

## Overview

<!-- Brief note on what this release contains at a high level. Process-focused: number of tasks, scope summary. Not technical detail. -->

{{RELEASE_OVERVIEW}}

---

## Task Artifact Verification

<!-- Verify that all approved tasks contributing to this release have their required artifacts present and accessible. PM checks existence and completeness — does not evaluate technical content. -->

### Required Artifacts Per Task

For each task contributing to this release, verify:

- [ ] `IMPLEMENTATION_REPORT.md` present (from Implementer)
- [ ] Test results documented (PASS/FAIL with notes)
- [ ] Review findings available (`REVIEW_REPORT.md`)
- [ ] CTO approval recorded (if applicable)
- [ ] Task status updated to CLOSED in tracking

| Task ID | Title | Artifacts Verified? | Notes |
|---------|-------|---------------------|-------|
| TASK-YYYYMMDD-NNN | <!-- title --> | ✅ / ❌ | <!-- any gaps --> |
| ... | ... | ... | ... |

---

## Documentation Synchronization

<!-- Verify that project documentation is consistent with the current code state. PM checks for sync, not correctness of technical content. -->

- [ ] `ROADMAP.md` reflects completed objectives and updated timeline
- [ ] `CHANGELOG.md` entries compiled from all contributing tasks (no duplicates)
- [ ] Architecture docs (`ARCHITECTURE.md`) updated if any structural changes were made
- [ ] Agent documentation (`AGENTS.md`, `SOUL.md`, etc.) consistent with current setup
- [ ] Milestone tracker (`milestone_tracker.md`) reflects current progress

---

## CHANGELOG Compilation

<!-- List of CHANGELOG entries pulled from individual task reports. PM compiles; does not write or edit technical descriptions. -->

### {{VERSION}} — {{DATE}}

**Scope**: <!-- Brief scope description (e.g., "v0.2.0 - Task management and tracking") -->

#### Added
- <!-- Entry from TASK-YYYYMMDD-NNN -->

#### Changed
- <!-- Entry from TASK-YYYYMMDD-NNN -->

#### Fixed
- <!-- Entry from TASK-YYYYMMDD-NNN -->

---

## Pre-Release Gate

<!-- Final verification before recommending release to CTO/User. PM reports status; does not approve the release itself. -->

| Check | Status | Notes |
|-------|--------|-------|
| All task artifacts present and verified | ✅ / ❌ | ... |
| Documentation synchronized | ✅ / ❌ | ... |
| CHANGELOG compiled (no gaps) | ✅ / ❌ | ... |
| Milestone tracking updated | ✅ / ❌ | ... |
| No unresolved blockers for this release | ✅ / ❌ | ... |

### Recommendation

<!-- PM's recommendation based on checklist results. -->

- [ ] **Ready for CTO/User review** — All checks passed, no outstanding gaps
- [ ] **Conditional readiness** — Minor items remain (see notes above)
- [ ] **Not ready** — Significant gaps identified; see blocked items section

---

*Release recommendation to be reviewed by: CTO agent / User*
