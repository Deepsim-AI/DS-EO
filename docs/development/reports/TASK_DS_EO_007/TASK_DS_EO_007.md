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
  - Repository sync
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
   tracking, milestone tracking, repository sync.
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
   ds-eo-openclaw/roles/pm.md, ds-eo-openclaw/protocols/status.md,
   ds-eo-openclaw/templates/status_report.md — adjust to match existing
   conventions).
8. Do not implement anything in this task — produce the plan only, for
   review before a follow-up implementation task is created.

Deliverable:
ds-eo-openclaw/docs/development/reports/TASK_DS_EO_007/PM_ROLE_PLAN.md
