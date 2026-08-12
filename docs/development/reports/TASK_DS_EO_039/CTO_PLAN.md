---
produced_by: ollama/qwen3.6:35b
session_id: 138093a6-6890-4ec8-bbdb-978bddb00071
produced_at: 2026-08-11T17:35:00-07:00
role: CTO
task_id: TASK_DS_EO_039
gate: G1
---

# CTO Plan: Run-State/Liveness Desynchronization Fix

## Acceptance Criteria

### AC1 — Abort Always Emits Lifecycle Event (Gateway)
After `abortEmbeddedAgentRun()` completes (whether a run was found or not), the gateway MUST emit at least one terminal lifecycle event (`phase:"end"` or `phase:"error"`) to all connected TUI clients for that session. This is non-optional — silent success with no events is prohibited.

**Test**: 10 consecutive `/abort` during active tool-use; verify each produces a terminal event.

### AC2 — "Finishing Context" Timeout (TUI)
`activityStatus === "finishing context"` MUST have an automatic timeout of ≤60 seconds. After timeout expires with no `phase:"end"`/`phase:"error"` received and no active run in gateway's registry, the TUI auto-clears to `"idle"` and logs a system message.

**Test**: Force TUI into "finishing context" state without sending any lifecycle events; verify it clears within 60s.

### AC3 — `/new` Unblocked When Runtime Says No Active Run
The `hasUnsafeSessionRollover()` gate MUST check gateway-side active run count before blocking. If gateway reports zero active runs for the session, `/new` is allowed regardless of stale TUI state. The TUI stale state is cleared as a side effect.

**Test**: Stale "finishing context" + no active run → `/new` succeeds and creates new session.

### AC4 — Post-Compact Abandoned State Cleanup
After compaction failure, all abandoned-run entries (`ABANDONED_EMBEDDED_RUNS_BY_SESSION_ID`, `activeRuns`, etc.) for the affected session MUST be cleaned up from gateway-side maps before any subsequent `/abort` or `/new` operations.

**Test**: Trigger compaction timeout during tool-use, then immediately `/abort`; verify no stale state remains.

### AC5 — Token Display Labeling
The TUI token display label MUST change from "context window usage" (implying actual context fill) to "cumulative turn cost" or similar unambiguous label that doesn't suggest overflow.

**Test**: Long tool-use session → verify display clearly indicates it's cumulative cost, not context fill percentage.

## Implementation Tasks

### Task 1 — Gateway abort event emission
**File**: `src/reply/agent-command` / `get-reply-OTG64ybi.js`
**Location**: After line 3579 (`logVerbose('Interrupting...')`)
**Change**: Add unconditional terminal lifecycle event emission when abort completes:
```javascript
// After the abort log line:
if (!aborted) {
    // No run was found to abort — still emit terminal event to clear TUI state
    const sessionHasActiveTUI = await hasActiveTUIForSession(sessionKey);
    if (sessionHasActiveTUI) {
        emitTerminalLifecycleEvent({
            sessionId: preparedSessionState.sessionId,
            phase: "end",
            status: "idle"
        });
    }
}
```

### Task 2 — TUI finishing-context timeout
**File**: `tui-ttOZNpsl.js`
**Location**: In `handleChatEvent` lifecycle event handler (line ~3454 area)
**Change**: Add watchdog timer:
```javascript
let staleFinishingTimer = null;
// After setActivityStatus("finishing context"):
clearTimeout(staleFinishingTimer);
staleFinishingTimer = setTimeout(() => {
    if (state.activityStatus === "finishing context" && 
        !state.activeChatRunId && 
        sessionRuns.size === 0) {
        setActivityStatus("idle");
        chatLog.addSystem("Stale finishing state cleared after timeout.");
    }
}, 60000);
```

### Task 3 — hasUnsafeSessionRollover gateway check
**File**: `tui-ttOZNpsl.js` (command handlers) or gateway-side check before returning rollover error
**Change**: Before blocking `/new`, verify gateway active run count. If zero, proceed anyway and clear TUI state:
```javascript
case "new":
    if (hasUnsafeSessionRollover()) {
        const hasActiveRun = await client.hasActiveRun(state.currentSessionKey);
        if (!hasActiveRun) {
            // Clear stale state — no actual run exists
            state.activeChatRunId = null;
            state.pendingChatRunId = null;
            state.pendingOptimisticUserMessage = false;
            state.activityStatus = "idle";
            break;  // Continue to session creation below
        }
        chatLog.addSystem("abort the current run before /new");
        tui.requestRender();
        break;
    }
```

### Task 4 — Post-compaction cleanup
**File**: `run-state-BteeOQT8.js`, `runs-B0SQhu92.js`
**Location**: In `abortActiveEmbeddedRunHandles()` and compaction error path
**Change**: After abort completion (successful or failed), explicitly prune abandoned entries for the session.

### Task 5 — Token display label
**File**: `tui-ttOZNpsl.js` or wherever token info is rendered
**Change**: Update label from "X/Y (Z%)" to "cumulative tokens used: X | context window: Y" to eliminate overflow confusion.

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Gateway event emission adds latency to abort response | Minimal — event is async, doesn't block abort completion |
| 60s timeout masks a real long-running operation | Acceptable tradeoff — TUI shows "finishing context" which signals the user |
| Gateway check in `hasUnsafeSessionRollover` requires client API | Implement as gateway-side guard before returning the error, not a separate RPC |

## Dependencies
- Depends on: None (this is an OpenClaw runtime fix)
- Related tasks: TASK_DS_EO_032 (abort state sync), TASK_DS_EO_033 (compaction timeout), TASK_DS_EO_038 (real spawn_agent CLI integration)

## Recommended Priority Order
1. Task 3 (TUI-side rollover check) — quickest win, client can detect stale state independently
2. Task 2 (finishing context timeout) — defense-in-depth, independent of gateway changes
3. Task 1 (gateway abort event) — fixes root cause, requires OpenClaw source change
4. Task 4 (post-compaction cleanup) — prevents recurrence in compaction scenarios
5. Task 5 (token label) — cosmetic improvement, low risk
