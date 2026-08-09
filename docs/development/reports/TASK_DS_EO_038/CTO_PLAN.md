---
produced_by: ollama/qwen3.6:35b
session_id: 9855be0e-7dce-433d-884f-5a77b8441dc9
produced_at: 2026-08-09T16:26:00-07:00
role: CTO
task_id: TASK_DS_EO_038
gate: G1
---

# CTO Plan — TASK_DS_EO_038: Phase 8 — Real `spawn_agent()` with OpenClaw CLI Integration

## Problem Statement

DS-EO's Dispatcher `spawn_agent()` returns mock/stub success without creating real agent sessions. This blocks the entire `/eco automatic mode` workflow — when PM auto-advances a task to implementation, no Implementer session is actually instantiated. The user explicitly deferred TASK_DAL_002 (TASK_DS_EO_037) on this dependency.

**Prior context**: TASK_DS_EO_026 diagnosed the defect and fixed baseline infrastructure; the actual OpenClaw CLI/sessions_spawn wiring was left as Phase 8.

## Scope

Build `spawn_agent()` so it:
1. Creates **real OpenClaw agent sessions** (not mock objects) via the appropriate platform API
2. **Verifies** each spawned session exists and is running before returning success
3. Returns a **usable session reference** (key/ID) that downstream agents can address

### Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| AC-1 | `spawn_agent()` creates a real OpenClaw session for the target agent role | Dispatch to Implementer, confirm session exists in OpenClaw session store |
| AC-2 | Returned session key/ID is valid and addresses the correct agent model | Verify target model matches requested role |
| AC-3 | PM can auto-advance G2 → Implementer gets real work via `spawn_agent()` | Run `/eo mode automatic`, advance a task, confirm Implementer executes |
| AC-4 | Verification step rejects phantom spawns (session creation fails → returns error) | Test failure path; confirm no mock success is returned |
| AC-5 | All existing dispatcher tests still pass + new spawn_verification test passes | Run full test suite |
| AC-6 | `/eco mode automatic` end-to-end: PM dispatches task → real Implementer session executes | Integration test, not unit test |

## Architecture Decision

### Why OpenClaw `sessions_spawn` Tool (not CLI)

The workspace runs on OpenClaw with the `sessions_spawn` tool available. The dispatcher should use this tool directly rather than shelling out to a CLI subprocess:

- **Reliability**: Direct tool call → no race conditions, no stub-by-mistake
- **Verification**: Tool returns session key immediately; we can check existence
- **Agent role binding**: Pass the target agent's model/prompt config as parameters

### Implementation Plan

#### Step 1: Identify the dispatcher module and current `spawn_agent()` stub (30 min)
- Locate `dispatcher/session_dispatcher.py` (or equivalent)
- Confirm which method is the spawn entry point
- Document what it currently does vs. what it should do

#### Step 2: Implement real spawn via OpenClaw tool integration (2 hours)
- Add `spawn_via_sessions_spawn()` that calls the OpenClaw `sessions_spawn` tool
- Pass target agent role → model mapping from agents config
- Return session key on success, error on failure

#### Step 3: Add verification layer (30 min)
- After spawn call, verify session exists in OpenClaw's session store
- Check that the session is running (not terminated)
- Only return "success" if both conditions hold

#### Step 4: Wire into PM auto-dispatch path (30 min)
- Confirm PM's `advance_g2()` → `spawn_agent()` call chain works end-to-end
- No changes to gate logic or protocol — this is purely infra, not governance

#### Step 5: Tests and integration verification (1 hour)
- Unit test: spawn creates session, verification passes
- Integration test: PM auto-mode dispatches task → real Implementer receives work
- Regression test: existing dispatcher tests still pass

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `dispatcher/session_dispatcher.py` (or equivalent) | EDIT | Replace stub with real spawn + verification |
| `tests/test_dispatcher_spawn.py` | NEW | Verification tests for spawn path |
| `ds_eo_openclaw/workflow/` (if needed) | REVIEW | Ensure no other stubs exist elsewhere |

## Risk Assessment: LOW

| Risk | Impact | Mitigation |
|------|--------|-----------|
| OpenClaw API surface may have changed since TASK_DS_EO_026 | Medium | Check current agent config and OpenClaw docs for sessions_spawn signature |
| Test suite breakage | Low | Run full 433-test suite after changes |
| Session model mismatch (role → model) | Low | Verify agents/*/md configs have correct model placeholders |

## Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ✅ Complete | CTO creates this task now |
| G1 (Plan Approved) | ⬜ Awaiting user approval | — |
| G2 (Implementation) | ⬜ Pending | After Implementer delivers |
| G3 (Review) | ⬜ Pending | After implementation complete |
| G4 (Final Approval) | ⬜ Pending | After Review passes |

## Notes to PM

- This is Phase 8 — the real `spawn_agent()` build the user deferred TASK_DAL_002 for
- The dependency chain: **Phase 8 complete → TASK_DS_EO_037 resumption possible**
- No new protocols needed — this is infrastructure, not governance change
- After G4 approval, PM should resume TASK_DS_EO_037 (TASK_DAL_002) with real spawn working
