# Dispatcher Skill — For the PM Agent

**Version**: 0.1.0  
**Purpose**: Teach the PM how to orchestrate tasks through DS-EO's dispatcher engine programmatically.

---

## When to Use This Skill

Use the dispatcher whenever you need to:
1. Start a new task (G0 → S0_OPEN)
2. Track current phase of any active task
3. Advance a task through gates G1-G4 programmatically
4. Handle rejections and revision loops
5. Detect stalls and escalate to CTO

---

## Quick Reference: Phase Map

| Phase | Agent | What Happens | Forward Transition |
|-------|-------|-------------|-------------------|
| S0_OPEN | PM | Create task skeleton, notify CTO | G0_ENTRY → S1_PLANNING |
| S1_PLANNING | CTO | Write CTO_PLAN.md, submit for approval | G1_APPROVE → S2_IMPLEMENTATION |
| S2_IMPLEMENTATION | Implementer | Execute plan, write IMPLEMENTATION_REPORT.md | G2_COMPLETE → S3_REVIEW |
| S3_REVIEW | Reviewer | Verify against plan, write REVIEW_REPORT.md | G3_APPROVE → S4_APPROVAL |
| S4_APPROVAL | CTO | Final approve/reject, write CTO_APPROVAL.md | G4_APPROVE → S5_COMPLETE |
| S5_COMPLETE | PM | Post-G4 cleanup, update project status | (terminal) |

---

## How to Start a Task

1. **Get task details from user**: What needs building? Priority? Reference spec?
2. **Request CTO to create the task directory** and assign an ID
3. **PM creates dispatcher state**: `docs/dispatcher/<TASK_ID>/dispatcher_state.json`
4. **Dispatch TASK_OPEN to CTO** via session_dispatch:
   ```python
   # Use sessions_spawn with context="isolated" targeting CTO
   # Prompt includes TASK_OPEN payload from communication_protocol.md
   ```
5. **Track in INDEX.md** and PROJECT_STATUS.md

---

## How to Advance Through Gates

### Gate G1 (Plan Approval)
When user says "APPROVE" on a plan:
1. Read dispatcher_state.json → confirm current_phase is S1_PLANNING
2. Verify CTO_PLAN.md exists in task directory
3. Execute G1_APPROVE transition:
   - Spawn Implementer via `sessions_spawn(agent="implementer", context="isolated")`
   - Use DELEGATE prompt template from workflow_defs/default.yaml
4. Update state to S2_IMPLEMENTATION

### Gate G2 (Implementation Complete)
When Implementer reports completion:
1. Read IMPLEMENTATION_REPORT.md in task directory
2. Verify against CTO's original plan scope
3. If confirmed complete → execute G2_COMPLETE transition
   - Spawn Reviewer via `sessions_spawn(agent="reviewer", context="isolated")`
   - Use review_request prompt template
4. Update state to S3_REVIEW

### Gate G3 (Review Complete)
When Reviewer submits REVIEW_REPORT.md:
1. Read the review report and scoring rubric
2. Report findings to user/CTO
3. If reviewer recommends APPROVE → execute G3_APPROVE transition
   - Spawn CTO via `sessions_spawn(agent="cto", context="isolated")`
   - Use approval_request prompt template
4. Update state to S4_APPROVAL

### Gate G4 (Final Approval)
When user approves final implementation:
1. Verify all artifacts present in task directory
2. Execute G4_APPROVE transition
3. Spawn PM (self) for post-G4 cleanup phase
4. Update state to S5_COMPLETE

---

## Rejection Handling

Any rejection produces a **revision loop** — work goes back to the producing agent:

| Rejection | From Phase | To Phase | Agent |
|-----------|-----------|----------|-------|
| G1 revision request | S1_PLANNING | S1_PLANNING | CTO revises plan |
| G2 incomplete | S2_IMPLEMENTATION | S2_IMPLEMENTATION | Implementer reworks |
| G3 changes requested | S3_REVIEW | S2_IMPLEMENTATION | Implementer fixes code |
| G4 reject | S4_APPROVAL | S2_IMPLEMENTATION | Implementer redoes work |

For each rejection:
1. Record the transition in state (`transition_history` array)
2. Log to `dispatch_log.jsonl`
3. Notify the relevant agent via `sessions_spawn(agent="...", context="isolated")` with revision details
4. Update phase tracking

---

## Stall Detection

Run stall checks periodically (during heartbeat or on task status queries):

1. Read dispatcher_state.json → check `stall_checks.current_phase_entered`
2. Check last artifact file modification time in task directory
3. If idle > 120 minutes OR phase entered > 480 minutes:
   - Set `stalled: true`
   - Create TASK_STALLED event
   - Spawn CTO for escalation
   - Notify user via PM_STATUS_UPDATE

---

## State Management Rules

- **Read state before every action** — never cache
- **Update state after every transition** — atomic write (temp file, rename)
- **Validate agent registry checksum** on each read — alert PM if mismatched
- **Never write outside your task directory** — only PM writes PROJECT_STATUS.md and CHANGELOG.md at workspace root
- **Append to dispatch_log.jsonl for every transition** — immutable audit trail

---

## Available Tools for Dispatcher Operations

The dispatcher uses these OpenClaw capabilities:
- `sessions_spawn(agent="...", context="isolated")` — spawn receiving agent session
- `sessions_send()` — send structured messages between sessions (fallback)
- `exec` — run git operations, file reads/writes for state management
- `memory_search` / `memory_get` — look up relevant task context
- `read` / `write` — manage state files and artifacts

---

## Error Patterns

| Error | What to Do |
|-------|-----------|
| Invalid transition (not in workflow) | Write TRANSITION_ERROR.md, alert user, do NOT proceed |
| Missing required artifact | Report which file is missing, do NOT block—guide agent to produce it |
| Agent not found in registry | Stop immediately, notify user that target agent needs to be registered |
| Gateway session spawn fails | Retry once after 2s delay; if still failing, write error and alert PM |
| Registry checksum mismatch | Halt all transitions, alert PM — agents_list.json has changed since task creation |

