TASK_DS_EO_007

Title:
PM Role Design and Responsibility Redistribution — Planning Only

Role:
CTO

Context:
DS-EO currently has three roles: CTO, Implementer, Reviewer. In practice,
CTO has absorbed responsibilities beyond architecture and technical
decisions — status tracking, engineering reports, documentation sync,
release checklists, changelog maintenance, and task lifecycle management
have all been sitting under CTO by default, since no other role owns them.

These are organizational/process responsibilities, not architectural ones.
Adding a PM role and redistributing responsibility as below narrows CTO back
to its actual purpose and gives task/status/release ownership a home:

CTO (narrowed):
  - Architecture
  - Technical decisions
  - Specifications
  - Approvals

PM (new):
  - Task tracking
  - Project status (PROJECT_STATUS.md)
  - Engineering report
  - Documentation (synchronization, not authoring technical content)
  - Repository lifecycle coordination (see precise definition below —
    PM coordinates and verifies, does not execute Git/GitHub operations
    itself)
  - Release notes / release checklist
  - Milestones
  - Task closure / task lifecycle

Implementer (unchanged, confirmed minimal):
  - Implement
  - Report blockers
  - Report deviations

Reviewer (unchanged, confirmed minimal):
  - Quality
  - Tests
  - Review
  - Compliance
  - Regression

This also reframes how OpenClaw relates to DS-EO conceptually:

  Before:  OpenClaw -> Agent
  After:   OpenClaw -> Organization -> Agents -> Protocols

I.e. DS-EO stops being "a set of agents you install" and becomes "an
organizational layer OpenClaw runs," with PM as the role that makes that
organization observable and self-tracking (status, reports, lifecycle)
rather than something only inferable from scattered task files.

Precise definition of PM's repository responsibility (do not leave this
ambiguous in the plan — "repository sync" must not be interpreted as "PM
has git-write/push authority"):

PM's role is to COORDINATE and VERIFY the repository lifecycle, not to
EXECUTE Git/GitHub operations. Responsibility split by stage:

  Stage                          | PM              | CTO              | Implementer
  --------------------------------|-----------------|------------------|------------------
  Verify task is complete         | Owns            | Reviews/approves | Provides deliverables
  Check documentation updated     | Owns            | Reviews if needed| Contributes
  Verify tests passed             | Owns            | Reviews          | Runs tests
  Prepare commit plan             | Owns            | Approves if significant | Executes/assists
  Commit message standard         | Owns            | Defines policy   | Follows policy
  Local Git commit                | Coordinates     | Approves milestone| Usually executes
  Tag release                     | Coordinates     | Approves         | Executes
  Push to GitHub/remote           | Coordinates after approval | Approves release/milestone | Executes
  Close task                      | Owns            | Final approval   | —

"Repository synchronization" means ensuring all project artifacts are
consistent before a task or milestone is closed, per this sequence:

  Implementation -> Tests Pass -> Documentation Updated -> Repository Clean
  -> Commit Created -> Tag Created (if milestone) -> Push to Remote (if
  configured) -> Task Closed

PM verifies this sequence is complete; PM does not necessarily type the Git
commands. Local and remote are treated separately:

  Local repository (always applies): PM checks git status is clean,
  unrelated files are excluded, commit groups are logical, commit messages
  follow convention, and the repo is in a releasable state — even when no
  remote is configured.

  Remote repository (GitHub/GitLab, only if one exists): approved commits
  and tags get pushed, the remote is verified to reflect local state, and
  the release/milestone is recorded. If no remote exists, the workflow
  simply stops after the local repository reaches a clean, approved state.

The underlying principle: none of PM's repository activities require
architectural decisions. "Should this task be closed?", "Has
PROJECT_STATUS.md been updated?", "Is CHANGELOG.md complete?" are PM
questions. "Should we use JWT or API keys?" is a CTO question. "How do we
implement JWT?" is an Implementer question. This keeps CTO focused on
technical leadership, not process administration.

Repository state machine (PM owns transitions from Review Passed through
Closed; CTO's involvement is limited to technical approval where required):

  Working -> Implementation Complete -> Review Passed ->
  Documentation Synchronized -> Repository Synchronized ->
  Released (optional) -> Closed

Naming note: do not name the resulting protocol file repository_sync.md —
that undersells its scope and hurts reusability across projects/hosts.
Prefer release_management_protocol.md or project_closure_protocol.md, with
repository synchronization (local Git and remote GitHub/GitLab) framed as
one step within that broader closure process, alongside documentation
updates, release notes, tagging, and task closure.

Relationship to TASK_DS_EO_006:
This task is independent of the role-enforcement/session-isolation work in
TASK_DS_EO_006 and may be planned in parallel. However, PM must be built on
top of the same session-isolation and identity-metadata mechanisms once
those land — a PM that silently absorbs status-writing into a CTO or
Implementer session would repeat the exact role-collapse problem found in
TASK_DS_EO_004. Note this dependency explicitly in the plan; do not assume
PM's protocols can skip isolation requirements.

Objective:
Produce a plan for introducing the PM role and redistributing existing
CTO responsibilities to it. This is a PLANNING task only — do not create
agent personas, modify openclaw.json, or alter existing protocol files.

Requirements:
1. Propose PM's persona scope (SOUL.md / IDENTITY.md outline) — what PM is
   responsible for, and explicitly what PM is NOT allowed to do (no
   architecture decisions, no code changes, no approval authority, no
   quality judgment).
2. Identify every existing artifact/responsibility currently produced by
   CTO that should move to PM: PROJECT_STATUS.md, engineering reports,
   changelog, release checklist, documentation sync, task lifecycle
   tracking, milestone tracking, repository lifecycle coordination (per
   the precise PM/CTO/Implementer split defined above — coordinate/verify,
   not execute).
3. For each moved responsibility, identify which existing protocol file(s)
   (planning.md, delegation.md, implementation.md, review.md, approval.md,
   completion.md, handoff.md) reference it, and what changes those files
   will need once PM owns it instead of CTO.
4. Define PM's position in the task lifecycle: where does PM sit relative
   to CTO approval and Reviewer sign-off? E.g. does PM open/track the task,
   CTO approve the spec, Implementer build, Reviewer check, PM close and
   log? Propose the explicit sequence.
5. Confirm PM's authority boundaries relative to CTO: PM should have
   process/tracking authority (can flag a task as stalled, can require a
   status update) but not decision authority (cannot override a CTO
   architectural call or a Reviewer's quality verdict). State this
   explicitly in the plan, matching the same authority distinction already
   used for session isolation in TASK_DS_EO_006.
6. Note the dependency on TASK_DS_EO_006: PM's artifacts (status reports,
   task closure records, etc.) must also carry agent_id/session_id/model
   metadata and must not be producible from a session that also acted as
   CTO, Implementer, or Reviewer on the same task.
7. Propose where PM fits in the repository structure (e.g.
   ds-eo-openclaw/roles/pm.md,
   ds-eo-openclaw/protocols/release_management_protocol.md (or
   project_closure_protocol.md — do not use repository_sync.md, see naming
   note above), ds-eo-openclaw/templates/status_report.md — adjust to
   match existing conventions).
8. Do not implement anything in this task — produce the plan only, for
   review before a follow-up implementation task is created.

Deliverable:
ds-eo-openclaw/docs/development/reports/TASK_DS_EO_007/CTO_PLAN.md


---

## Closure — 2026-07-30 (Task Update)

This task was originally created on 2026-07-28 as a planning-only task. On
2026-07-30 we verified the current state:

### Implementation Status

All implementation steps from the CTO Plan (§9) were completed during the
initial deployment commit (489a03a, 2026-07-28), not via a dedicated
TASK_DS_EO_008 as originally recommended. The work was done inline by the
deployment process, not by a separate follow-up task.

**All 7 items verified present:**

| Priority | Step | Artifact | Status |
|----------|------|----------|--------|
| P0 | 1 | `agents/pm.md` | ✅ Present (146 lines) |
| P0 | 2 | PM entry in `ds_eo_manifest.yaml` | ✅ Present (lines 47–50, 101) |
| P1 | 3 | `protocols/release_management_protocol.md` | ✅ Present |
| P1 | 4 | Protocol updates (4 files) | ✅ delegation + handoff + completion + communication all updated |
| P1 | 5 | Templates (4 files) | ✅ task_status + engineering_report + release_checklist + milestone_tracker |
| P2 | 6 | `verify_task_artifacts.sh` Phase 5 | ✅ `validate_pm_artifacts()` at line 291 |

### Dependency Check

§6 dependency on TASK_DS_EO_006: **SATISFIED** — TASK_DS_EO_006 is approved
and deployed. Session-isolation and identity metadata mechanisms are active.

### Files Requiring Attention

- `CTO_PLAN.md` — untracked in git (add to repo)
- `PM_ROLE_PLAN.md` — exists only as a git-deleted file on disk; consider
  consolidating with CTO_PLAN.md
- No `REVIEW_REPORT.md` or `CTO_APPROVAL.md` produced (this was a planning
  task, not an implementation task)

### Task Status: COMPLETE

All acceptance criteria met (8/8). Plan remains architecturally sound. No
revisions to the plan content are needed. The task is ready for closure.
