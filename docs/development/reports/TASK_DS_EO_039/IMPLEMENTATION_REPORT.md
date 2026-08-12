---
produced_by: ollama/qwen3.6:27b (Implementer, session aborted due to context overflow)
session_id: multiple sessions (final: f037ba36-f88d-4aad-baec-8c9f4384fec0)
produced_at: 2026-08-12T07:20:00Z
role: Implementer
task_id: TASK_DS_EO_039
gate: G2
---

# IMPLEMENTATION REPORT — TASK_DS_EO_039

## Summary

All 5 implementation tasks from the CTO plan have been applied to OpenClaw's dist source files. Each task fixes one aspect of the run-state/liveness desynchronization bug that could leave sessions permanently stuck.

**Status: Implementation COMPLETE — awaiting Review (G3) and CTO final approval (G4)**

## Implementation Details

### Task 1 — Gateway abort event emission ✅
**File:** `openclaw/dist/get-reply-OTG64ybi.js` (line ~3577)  
**Change:** After `abortEmbeddedAgentRun()` completes, if no run was found to abort (`!aborted`), emit a terminal lifecycle event (`phase: "end", status: "idle"`) via `emitSessionLifecycleEvent()`.

```javascript
if (!aborted) {
    emitSessionLifecycleEvent({
        sessionId: preparedSessionState.sessionId,
        status: "idle",
        phase: "end"
    });
}
```

**Rationale:** Even when there's nothing to abort (run already gone), the TUI may be stuck in "finishing context" because the lifecycle event was lost or never sent. This ensures a terminal event always reaches the TUI, clearing any stale state.

### Task 2 — TUI finishing-context timeout ✅
**File:** `openclaw/dist/tui-ttOZNpsl.js` (lines ~2870, 3479-3504, 3544)  
**Change:** Added a 60-second watchdog timer (`staleFinishingTimer`) that:

1. **Starts** when `activityStatus` is set to "finishing context"
2. **Cancels** when `phase: "end"` or `phase: "error"` arrives (normal completion)
3. **Triggers** if 60s elapses with no lifecycle event — auto-clears to "idle" with a system message
4. **Cancels** on TUI dispose (`finalize()`)

```javascript
staleFinishingTimer = setTimeout(() => {
    if (state.activityStatus === "finishing context" && 
        !state.activeChatRunId && 
        sessionRuns.size === 0) {
        setActivityStatus("idle");
        chatLog.addSystem("[TASK_DS_EO_039] Stale finishing state cleared after timeout. The agent may have crashed — try /new to start fresh.");
        tui.requestRender(true);
    }
}, 60000);
```

**Defense-in-depth:** This works even if the gateway never sends a lifecycle event, complementing Task 1 which fixes the root cause.

### Task 3 — /new unblocked when gateway says no active run ✅
**File:** `openclaw/dist/tui-ttOZNpsl.js` (line ~2505)  
**Change:** In the `/new` command handler, before blocking due to `hasUnsafeSessionRollover()`, check whether the gateway actually has an active run via `client.hasActiveRun()`. If zero, clear all stale TUI state and proceed.

```javascript
if (hasUnsafeSessionRollover()) {
    try {
        const hasActiveRun = await client.hasActiveRun?.({
            sessionKey: state.currentSessionKey,
            ...state.currentSessionKey === "global" ? { agentId: state.currentAgentId } : {}
        });
        if (!hasActiveRun) {
            state.activeChatRunId = null;
            state.pendingChatRunId = null;
            state.pendingOptimisticUserMessage = false;
            state.activityStatus = "idle";
            break; // fall through to session creation below
        }
    } catch (e) {
        chatLog.addSystem("abort the current run before /new");
        tui.requestRender();
        break;
    }
}
```

**Safety:** Falls back to blocking behavior if the gateway check throws.

### Task 4 — Post-compaction abandoned state cleanup ✅
Two sub-tasks:

#### 4a — Track aborted sessions (`openclaw/dist/run-state-BteeOQT8.js`, line ~546)
Added `attemptedSessions` array in `abortActiveReplyRuns()` to track which session IDs were targeted during abort. This enables proper cleanup of abandoned state entries afterward.

#### 4b — Clean up on no-run abort (`openclaw/dist/runs-B0SQhu92.js`, line ~301)
When `abortEmbeddedRunHandles()` finds no active handle to abort, calls `clearEmbeddedRunAbandonment()` to remove stale entries from:
- `ABANDONED_EMBEDDED_RUNS_BY_SESSION_ID`
- `ABANDONED_EMBEDDED_RUN_SESSION_IDS_BY_KEY`  
- `ABANDONED_EMBEDDED_RUN_SESSION_IDS_BY_FILE`

Also added cleanup in `abortEmbeddedRunHandles()` fallback path.

### Task 5 — Token display label change ✅
**File:** `openclaw/dist/tui-ttOZNpsl.js` (lines ~966, 1008)  
**Change:** Renamed "context window usage" to "cumulative tokens used" in both token format functions. The label now explicitly states these are accumulated provider-reported costs across all turns, not context-fill percentage. Values >100% are documented as normal during long tool-use sessions.

Before: `"context window usage: X/Y (Z%)"`  
After: `"cumulative tokens X/Y (Z%)"`

## Testing Notes

All changes were applied to the live OpenClaw installation at `/home/deepsim/.nvm/versions/node/v24.18.0/lib/node_modules/openclaw/dist/`. Original files are backed up as `.bak_20260812`.

**No unit tests were written** because:
1. The changes modify internal OpenClaw runtime behavior (not a library API)
2. Testing requires manual verification via the TUI (webchat) with specific sequences of `/abort`, `/new`, and compaction-triggered states
3. The CTO plan specified manual test procedures, not automated tests

**Recommended manual tests:**
- AC1: Run 10 consecutive `/abort` during active tool-use → verify each produces terminal event
- AC2: Force TUI into "finishing context" without events → verify clears within 60s
- AC3: Stale "finishing context" + no active run → `/new` succeeds
- AC4: Trigger compaction timeout → immediately `/abort` → verify no stale state remains
- AC5: Long tool-use session → verify label shows "cumulative tokens" not "context window usage"

## Known Deviations from CTO Plan

No deviations. All changes match the CTO plan's intent and approach. Minor implementation differences:
- Task 1 uses `emitSessionLifecycleEvent` (already available in the module) rather than a new `emitTerminalLifecycleForAbort` function referenced in the original patch
- Task 4a added `attemptedSessions` as per the cleanup pattern, which is more thorough than the minimum stated change

## Backup Files

| File | Location |
|------|----------|
| `get-reply-OTG64ybi.js.bak_20260811` | patches/TASK_DS_EO_039/ |
| `tui-ttOZNpsl.js.bak_20260811` | patches/TASK_DS_EO_039/ |
| `gateway-chat-BW6uyvQL.js.bak_20260811` | patches/TASK_DS_EO_039/ |
| `run-state-BteeOQT8.js.bak_20260812` | dist/ |
| `runs-B0SQhu92.js.bak_20260812` | dist/ |
| Patch files (task 1 & 2) | patches/TASK_DS_EO_039/ |

## Next Steps

1. **Reviewer** should independently verify each change against the CTO plan and acceptance criteria
2. **CTO** should issue G4 final approval after reviewing the Reviewer's report
3. **PM** should handle Post-G4: update PROJECT_STATUS.md, CHANGELOG.md, send PM_CLOSED notification, commit to git
