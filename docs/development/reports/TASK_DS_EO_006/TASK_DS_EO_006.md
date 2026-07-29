TASK_DS_EO_006

Title:
Implement Role Separation Enforcement (Session Isolation, Identity Metadata,
Verification, Reviewer Persona)

Role:
CTO (plan/oversee) + Implementer (execute)

Context:
CTO_ROLE_ENFORCEMENT_ANALYSIS.md (TASK_DS_EO_005) confirmed three independent
failures behind TASK_DS_EO_004's self-review/self-approval:

1. Configuration-level role collapse — Reviewer has its own model
   (laguna-xs-2.1:q4_K_M) and session directory, but no distinct persona;
   all agents currently share a generic SOUL.md.
2. Session-continuity self-review — one continued session produced
   Implementer, Reviewer, and CTO artifacts sequentially with shared context.
3. Protocol/verification gaps — no artifact records session ID or agent ID;
   verify_task_artifacts.sh only checks file existence, not identity.

Critically, the analysis confirmed OpenClaw already supports genuine session
isolation via sessions_spawn(context="isolated") — this is a protocol
enforcement gap, not a platform capability gap. The fix is to mandate use of
a capability that already exists, not to build new infrastructure.

Before implementation begins:
CTO_ROLE_ENFORCEMENT_ANALYSIS.md must receive one independent human review
(manual, by the project owner) before this task starts. This report was
authored by the CTO agent; given this task changes the approval-integrity
mechanism itself, it should not be the first thing self-approved under the
old, broken process.

Objective:
Implement proposals D, B, C, and A from CTO_ROLE_ENFORCEMENT_ANALYSIS.md, in
that priority order, so that review and approval artifacts can no longer be
produced by a session, context, or identity that overlaps with the work
being reviewed or approved.

Sequencing and Requirements:

Step 1 — Proposal D: Mandatory Session Isolation (do first — structural fix)
1a. Update implementation_protocol.md, review_protocol.md, and
    approval_protocol.md to require sessions_spawn(context="isolated") at
    every role transition (Implementer -> Reviewer -> CTO).
1b. Explicitly prohibit continuing a single session across role boundaries,
    including after gateway disconnects/reconnects — a reconnect must
    resume within the same role's session, never advance into the next
    role's artifact.
1c. Document what happens if a session disconnects mid-role: it should
    resume or restart within that same role, not silently continue into
    the next role's work.

Step 2 — Proposal B: Identity Metadata in Handoff Artifacts
2a. Add agent_id, session_id, and model fields to IMPLEMENTATION_REPORT.md,
    REVIEW_REPORT.md, and CTO_APPROVAL.md templates.
2b. Metadata must be injected by the OpenClaw runtime at session-spawn time,
    not self-declared by the agent in the artifact body — self-reported
    identity is not trustworthy for an integrity check. Confirm this is
    possible; if not, flag as an open risk rather than proceeding as if
    solved.

Step 3 — Proposal C: Verification Script Update
3a. Update verify_task_artifacts.sh to fail when:
    - reviewer agent_id/session_id/model matches implementer's, or
    - approver (CTO) agent_id/session_id matches reviewer's or implementer's.
3b. Verification must read identity from the runtime-injected metadata
    (Step 2b), not from any self-declared field.
3c. Re-run against TASK_DS_EO_004 to confirm it now correctly fails.

Step 4 — Proposal A: Distinct Reviewer Persona
4a. Create a dedicated SOUL.md / IDENTITY.md for the Reviewer role, distinct
    from CTO/Architect and Implementer, defining its scope (evaluates
    against acceptance criteria, cannot modify code, cannot approve).
4b. Confirm Reviewer's existing model (laguna-xs-2.1:q4_K_M) is correctly
    wired to load this new persona, not the generic SOUL.md.
    (Note: this step is content-only and may be executed in parallel with
    Steps 1-3 if capacity allows, but must not be marked complete until
    verified against the new isolated-session + metadata mechanism.)

Step 5 — Proposal E: Revoke and Re-review TASK_DS_EO_004
5a. Create ds-eo-openclaw/docs/development/reports/TASK_DS_EO_004/TASK_REVOCATION.md
    to formally invalidate the existing REVIEW_REPORT.md and CTO_APPROVAL.md.
    NOTE: exact structure of TASK_REVOCATION.md not confirmed — use existing
    repo convention/template if one exists; if not, include at minimum:
      - status: REVOKED
      - reason: review and approval were produced under a role-collapsed
        process (see TASK_DS_EO_005 findings #1 and #2) — reviewer identity
        matched CTO/Architect (ollama/qwen3.6:35b) rather than a distinct
        Reviewer persona, and all three handoff artifacts were produced in
        a single continued session with shared context.
      - revoked_artifacts: REVIEW_REPORT.md, CTO_APPROVAL.md (original)
      - revoked_by: (session/agent_id performing the revocation)
      - next_step: mandatory re-review under enforced role separation
        (Steps 1-4 of this task)
5b. Once Steps 1-4 are live, re-run TASK_DS_EO_004 through review and
    approval under the enforced process, using a genuinely isolated
    Reviewer session with the new persona.
5c. Record the outcome as new REVIEW_REPORT.md and, if applicable,
    CTO_APPROVAL.md files. Follow whatever naming/versioning convention the
    repo already uses for re-reviews after a revocation (e.g. if prior
    revocations exist elsewhere in the repo, match that pattern exactly
    rather than inventing a new one).

Constraints:
- Do not skip Step 1 (D) in favor of starting with A — persona work without
  session isolation would only make self-review look more convincing, not
  fix it.
- Each step's completion must itself be verified by a session distinct from
  the one that implemented it, per the very rule this task is establishing.
  Apply the new process to this task's own review, once Steps 1-3 exist.

Deliverable:
ds-eo-openclaw/docs/development/reports/TASK_DS_EO_006/IMPLEMENTATION_REPORT.md
ds-eo-openclaw/docs/development/reports/TASK_DS_EO_006/REVIEW_REPORT.md
ds-eo-openclaw/docs/development/reports/TASK_DS_EO_004/TASK_REVOCATION.md
ds-eo-openclaw/docs/development/reports/TASK_DS_EO_004/REVIEW_REPORT.md (re-review, post-revocation)
ds-eo-openclaw/docs/development/reports/TASK_DS_EO_004/CTO_APPROVAL.md (re-approval, if applicable)
