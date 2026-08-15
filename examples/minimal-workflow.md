# Minimal Workflow Example — From Request to Delivery

This walkthrough demonstrates a complete task cycle using DS-EO on OpenClaw. It shows what happens at each phase and gate, including the Project Manager's lifecycle coordination role.

---

## Scenario

A user requests: "Switch to automatic execution mode and run the pending TASK_20260803_001 task."

---

# ───────────────────────────────────────────────
# MANUAL MODE — Step by Step
# ───────────────────────────────────────────────

## Phase 1: Planning (CTO)

### User sends request to PM

The user is on their own chat session (e.g., webchat). They send:

```
/eo task "Switch to automatic execution mode and execute TASK_20260803_001"
```

This routes to the **PM agent** via gateway binding.

### G0 Intake (PM or CTO) — whoever receives the request creates the folder

If routed through PM:
1. PM creates task directory: `docs/development/reports/TASK_<NNN>/`
2. PM writes `TASK_REQUEST.md` with verbatim user request and captured requirements
3. PM acquires/releases folder lock (`LOCK.md`)
4. PM sends READY_FOR_CTO handoff message to CTO

If routed through CTO directly:
1. CTO creates task directory and assigns ID
2. CTO writes `TASK_REQUEST.md` with verbatim user request and confirmed requirements
3. CTO proceeds to independent architectural analysis (G1 planning)

### G1 Planning (CTO)

The CTO (in its own isolated session):
3. Reads the relevant spec (or derives one from the request)
4. Analyzes existing code in `config/parse.py`
5. Writes `CTO_PLAN.md`:

```markdown
# CTO Implementation Plan — TASK_20260728_001

## Problem Statement
Configuration parser accepts invalid inputs without validation,
leading to runtime errors downstream.

## Current State
- `config/parse.py` has a `parse_config()` function that returns raw strings
- No input length checking exists
- Numeric fields are cast with `int()` but never validated before cast

## Proposed Changes
1. Add `_validate_string()` helper: checks non-empty, ≤256 chars
2. Add `_validate_int()` helper: checks format matches `-?\d+`
3. Integrate validators into `parse_config()` for all input fields
4. Add comprehensive tests in `tests/test_parse_validation.py`

## Acceptance Criteria
1. Empty strings raise ValueError with descriptive message
2. Strings >256 chars raise ValueError with length info
3. Non-integer numeric inputs raise ValueError with format example
4. All existing tests still pass (no regressions)
5. New test file covers ≥90% of validation paths

## Risks
- R1: Backward compatibility — callers may depend on unvalidated behavior
  → Mitigation: Add deprecation warning for first release, error in v2
```

### Gate G1: User Approves Plan

**The user must review the plan and take explicit action.** In manual mode nothing auto-advances. The user sees the CTO's work through one of two channels:
- PM reports back: "CTO plan is ready for your review — see `docs/development/reports/TASK_20260728_001/CTO_PLAN.md`"
- User reads the file directly

The user responds with either:
```
APPROVE                    ← Proceeds to implementation
REVISE: [specific feedback] ← Returns to CTO for revision
```

---

# ───────────────────────────────────────────────
# AUTOMATIC MODE — Step by Step (Full Session Lifecycle)
# ───────────────────────────────────────────────

The automatic mode uses **isolated sessions** — each agent gets its own session. The user interacts only at two gates (G1 and G4). Here is the complete session lifecycle:

## Session Timeline

```
Session A: User → PM                    ← User initiates via /eo task
Session B: PM → CTO (spawned isolated)  ← CTO creates plan
Session C: User reviews + says APPROVE  ← Gate G1 — USER interaction
Session D: PM → Implementer (spawned)   ← Implementer writes code
Session E: PM → Reviewer (spawned)      ← Reviewer verifies
Session F: PM → CTO (spawned)           ← CTO makes final decision
Session G: User reviews + says APPROVE  ← Gate G4 — USER interaction
Session H: PM Post-G4 cleanup            ← Auto-complete
```

### Step 1: User initiates (Session A — User/PM)

The user is on their own chat session. They send:

```
/eo task "Add input validation to config parser"
```

**What happens:**
- Gateway routes `/eo task` → PM agent (via binding)
- PM creates the task directory: `docs/development/reports/TASK_20260805_001/`
- PM writes `TASK_REQUEST.md` with the verbatim user request and captured requirements
- PM acquires folder lock (`LOCK.md`, status active), then releases it
- PM creates `dispatcher_state.json` with S0_OPEN state
- PM sends READY_FOR_CTO handoff and spawns an isolated CTO session

**User sees:** The PM replies in their session: "Task TASK_20260805_001 created. CTO is writing the plan."

### Step 2: CTO writes plan (Session B — CTO, isolated)

The CTO (in a new, isolated session — user never sees this session):
- Receives TASK_OPEN context via spawn payload
- Creates task directory, reads spec, writes `CTO_PLAN.md`

**User sees:** Nothing during planning. The PM monitors the artifact and later reports status.

### Step 3: Gate G1 — User approves (Session A — User/PM)

The PM auto-detects that CTO_PLAN.md exists (`detect_state()` returns G1_WAITING) and notifies the user:

```
Status: Plan submitted for review
Artifact: docs/development/reports/TASK_20260805_001/CTO_PLAN.md
Action required: Approve or request revision.
```

**The user MUST read CTO_PLAN.md and respond.** In automatic mode, the PM does NOT approve on the user's behalf. The user replies in their session with:
```
APPROVE
```

### Step 4: Implementation (Session D — Implementer, isolated)

After user says APPROVE:
- PM spawns an isolated Implementer session via `sessions_spawn(agent="implementer", context="isolated")`
- The Implementer writes code per the CTO's plan
- The Implementer runs tests and writes `IMPLEMENTATION_REPORT.md`

**User sees:** A status message from the system (via auto-notification):
```
Status: G2 passed automatically — Review started
Artifact: IMPLEMENTATION_REPORT.md produced at docs/development/reports/TASK_20260805_001/
```
The user does NOT see the Implementer's session content.

### Step 5: Review (Session E — Reviewer, isolated)

PM auto-detects `IMPLEMENTATION_REPORT.md` exists → auto-advances to REVIEW state → spawns isolated Reviewer session.

The Reviewer inspects code quality and writes `REVIEW_REPORT.md`.

**User sees:**
```
Status: Review complete. Awaiting CTO G3 evaluation.
Recommendation: APPROVE_WITH_COMMENTS (score 4.65/5)
Artifact: docs/development/reports/TASK_20260805_001/REVIEW_REPORT.md
```

### Step 6: Final approval decision (Session F — CTO, isolated)

PM auto-detects `REVIEW_REPORT.md` exists → spawns isolated CTO session for G4.

The CTO reviews both reports independently and writes `CTO_APPROVAL.md`.

**User sees:** Nothing during the CTO's G4 evaluation. The PM notifies when ready for the user's decision.

### Step 7: Gate G4 — User approves (Session A — User/PM)

The system notifies the user that a final decision is ready:

```
Status: Final approval required
Artifact: docs/development/reports/TASK_20260805_001/CTO_APPROVAL.md
Decision: CTO recommends APPROVE (score 4.65/5)
Action required: Approve to complete, or reject for rework.
```

**The user MUST review and respond.** They reply in their session with:
```
APPROVE
```

### Step 8: Post-G4 cleanup (Session H — PM)

After user says APPROVE at G4:
- PM auto-advances to S5_COMPLETE via `advance_g4(approved=True)`
- PM updates `PROJECT_STATUS.md`, `CHANGELOG.md`
- PM writes `PM_CLOSED.md`
- PM commits to Git (requires user confirmation for remote push)

**User sees:**
```
Status: Task completed, cleanup in progress.
All artifacts verified. Changelog updated.
Ready for git push — please confirm target repo and branch.
```

---

# ───────────────────────────────────────────────
# Summary of User Interactions
# ───────────────────────────────────────────────

## Manual Mode — User Must Do Everything

| Step | What User Does | Session They're In |
|------|---------------|-------------------|
| 1 | Send `/eo task` with request | Their own session (routes to PM) |
| 2 | Read CTO_PLAN.md, say "APPROVE" | Their session |
| 3 | Verify IMPLEMENTATION_REPORT.md is correct | Check file directly or ask PM |
| 4 | Say "implementation done" to PM | Their session (triggers G2 advance) |
| 5 | Read REVIEW_REPORT.md, advise on review findings | Their session |
| 6 | Say "advance to review" to PM | Their session (triggers G3 advance) |
| 7 | Read CTO_APPROVAL.md, say "APPROVE" at G4 | Their session |
| 8 | Confirm git push repo + branch | Their session |

**User touches:** Every gate and transition explicitly.

## Automatic Mode — User Only Touches G1 and G4

| Step | What User Does | Session They're In |
|------|---------------|-------------------|
| 1 | Send `/eo task` with request | Their own session (routes to PM) |
| 2–3 | Read CTO_PLAN.md, say "APPROVE" at G1 | Their session — **first required interaction** |
| 4–6 | (No action needed) | System auto-advances through all intermediate phases |
| 7 | Read CTO_APPROVAL.md, say "APPROVE" at G4 | Their session — **second required interaction** |
| 8 | Confirm git push repo + branch | Their session |

**User touches:** Only gates G1 and G4. Everything between (implementation, review, CTO evaluation) happens automatically via isolated agent sessions. The user can check status at any time by asking the PM: "What's the current status of TASK_20260805_001?"

---

## Where Messages Go — Session Routing Reference

| Event | From Agent | To Agent (via) | User Sees It? |
|-------|-----------|----------------|---------------|
| Task created | PM | CTO (via `sessions_spawn`) | No — CTO's session is isolated |
| Plan ready | CTO → PM | PM reports to user | Yes (summary from PM) |
| G1 approve | User | PM (direct) | Yes — in user's own session |
| Implementer delegated | PM | Implementer (via `sessions_spawn`) | No — Implementer's session is isolated |
| Review started (auto) | StateEngine auto-detects | PM notifies user | Yes ("G2 passed automatically") |
| Review complete (auto) | StateEngine auto-detects | PM notifies user | Yes ("Review complete. Awaiting CTO G3 evaluation.") |
| G4 decision ready | CTO → PM | PM notifies user | Yes — with recommendation summary |
| Task completed (auto) | StateEngine auto-detects | PM notifies user | Yes ("Task completed, cleanup in progress") |

### Key Principle: Isolated Sessions

Every cross-phase handoff uses `sessions_spawn(agent="...", context="isolated")`. This means:
- The user's session is **never** the Implementer's session or the Reviewer's session
- Each agent works in its own isolated context — no shared chat history between phases
- The user only interacts with PM (for task management) and directly at G1/G4 gates
- Status messages about intermediate phases come from the PM, not from the executing agents

### Auto-Mode User Notifications (from `notifications.py`)

These are automatically sent by the StateEngine/PM to the user's chat surface:

| When | Notification Message |
|------|---------------------|
| Plan submitted for review | "Plan submitted for review" |
| G2 passed, reviewer assigned | "G2 passed automatically — Reviewer assigned" |
| Review complete, CTO evaluating | "Review complete. Awaiting CTO G3 evaluation." |
| Task completed, cleanup started | "Task completed, cleanup in progress" |
| Changes requested (revision loop) | "Changes requested: [reason] — rework required" |
| Blocker detected | "BLOCKER: [details]" (urgent priority) |
| Task stalled (timeout) | "STALLED: last activity [timestamp], exceeded timeout" (warning priority) |

---

## Notes

- **Post-G4 isolation**: Per AGENTS.md §11b, PM closure duties occur in a separate session from G4 approval.
- **Artifact author tracking**: All agent-produced artifacts include `produced_by` metadata (AGENTS.md §11e). Self-authored reviews across roles are prohibited.
- **Mode switching**: Users can toggle between manual and automatic mode at any time using `/eo mode <mode>`. Per-task overrides are also supported via `/eo mode override TASK_<id> <mode|off>`.
- **Automatic mode does NOT mean "no user involvement"** — the user still approves at gates G1 and G4. Automatic means the state engine handles everything *between* those gates automatically.
