---
produced_by: ollama/qwen3.6:35b
session_id: d8230282-d079-4f2d-8e74-ce3ceb190383
produced_at: 2026-08-11T21:55:00-07:00
role: CTO
task_id: TASK_DS_EO_039
gate: G2
---

# IMPLEMENTER DISPATCH — TASK_DS_EO_039

## Approved Plan Summary

Implement all 5 tasks from the approved CTO plan. Priority order:

### Task 1 — Gateway abort event emission
**File**: `src/reply/agent-command` / `get-reply-OTG64ybi.js`
**Location**: After line 3579 (`logVerbose('Interrupting...')`)
**Change**: Add unconditional terminal lifecycle event emission when abort completes:
```javascript
if (!aborted) {
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
**File**: `tui-ttOZNpsl.js` in `handleChatEvent` lifecycle event handler (~line 3454)
**Change**: Add watchdog timer after `setActivityStatus("finishing context")`:
```javascript
let staleFinishingTimer = null;
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
**File**: `tui-ttOZNpsl.js` (command handlers)
**Change**: Before blocking `/new`, verify gateway active run count. If zero, clear stale state and proceed:
```javascript
case "new":
    if (hasUnsafeSessionRollover()) {
        const hasActiveRun = await client.hasActiveRun(state.currentSessionKey);
        if (!hasActiveRun) {
            state.activeChatRunId = null;
            state.pendingChatRunId = null;
            state.pendingOptimisticUserMessage = false;
            state.activityStatus = "idle";
            break;
        }
        chatLog.addSystem("abort the current run before /new");
        tui.requestRender();
        break;
    }
```

### Task 4 — Post-compaction cleanup
**Files**: `run-state-BteeOQT8.js`, `runs-B0SQhu92.js`
**Change**: In `abortActiveEmbeddedRunHandles()` and compaction error path, explicitly prune abandoned entries for the session after abort completion.

### Task 5 — Token display label
**File**: `tui-ttOZNpsl.js` or wherever token info is rendered
**Change**: Update label from "X/Y (Z%)" to "cumulative tokens used: X | context window: Y"

## Deliverables Required
1. Code changes for all 5 tasks
2. Test results for each acceptance criterion
3. Implementation report at `IMPLEMENTATION_REPORT.md`
4. Return completed work to CTO + Reviewer

## Important Notes
- Follow the plan exactly — no independent architectural decisions
- If ambiguity is encountered, stop and return to CTO
- All changes should be minimal and targeted to the specific files identified
