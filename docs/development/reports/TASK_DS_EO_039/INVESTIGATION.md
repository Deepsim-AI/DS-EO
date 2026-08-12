---
produced_by: ollama/qwen3.6:35b
session_id: 138093a6-6890-4ec8-bbdb-978bddb00071
produced_at: 2026-08-11T17:32:00-07:00
role: CTO
task_id: TASK_DS_EO_039
gate: G1
---

# Investigation: Run-State/Liveness Desynchronization Deadlock

## Executive Summary

A critical control-plane deadlock occurs when the OpenClaw gateway's actual embedded-run runtime has **no active run** (because it was aborted/killed), but the TUI webchat's local state still believes a run is active (`activeChatRunId` set, `activityStatus === "finishing context"`). This creates an impossible state where both `/abort` and `/new` are blocked, leaving the session permanently unusable until Ctrl+C restart.

Root cause: **a TOCTOU race between the gateway-side run abort and TUI-side lifecycle event processing**, combined with a **stale `activityStatus === "finishing context"` sentinel that has no timeout or forced-clear mechanism**. The gatekeeping function `hasUnsafeSessionRollover()` blocks all session mutations, not just new runs.

This is a **severe control-plane liveness bug** — not cosmetic. It prevents any further agent execution without external intervention (Ctrl+C).

---

## 1. Architecture of the Run-State Pipeline

The run state flows through two independent state machines that must stay synchronized:

```
┌─────────────────────┐        lifecycle events         ┌──────────────────┐
│ Gateway-side runtime │ ◄════════════════════════════► │ TUI webchat TUI  │
│                      │                                 │ (tui-ttOZNpsl.js) │
│                      │                                 │                  │
│ ACTIVE_EMBEDDED_RUNS │        phase:"start"            │ activeChatRunId: null
│ (Map<sessionId,run>) │ ◄──── run starts ────►         │ activityStatus: "idle"
│                      │                                 │                  │
│ embedded runs killed/│        phase:"finishing"        │ activeChatRunId: <id>
│ removed from map     │ ◄──── compaction/abort ──►     │ activityStatus: "running"
│                      │                                 │                  │
│ ACTIVE_EMBEDDED_RUNS │        phase:"end"/"error"      │ activeChatRunId: <id>
│ becomes empty        │ ◄──── completed ────────►      │ activityStatus: "finishing"
│ (runtime says no     │                                 │ context          │
│  active run)         │        (event lost/not received)│                  │
└─────────────────────┘                                 │                  │
                                                        │ activeChatRunId: <stale_id>  ← STALE
                                                        │ activityStatus: "finishing"  ← STALE
                                                        └──────────────────┘
```

**Key insight**: The TUI's `activeChatRunId` is the *only* thing that controls whether `/new` and `/abort` are allowed. It lives in the TUI's client-side JavaScript state, not in any server/durable store. When it becomes stale, no TUI command can recover from it because the recovery commands check against the very same stale state.

---

## 2. Answering the Seven Questions

### 2.1 What is the authoritative source of run state?

**Two authoritative sources exist, and they are intentionally independent:**

| Authority | Location | What It Controls |
|-----------|----------|------------------|
| **Gateway-side runtime** (`run-state-BteeOQT8.js`) | Server process memory; `ACTIVE_EMBEDDED_RUNS`, `ABANDONED_EMBEDDED_RUNS_BY_SESSION_ID` Maps | Whether a model run is actually executing, queue scheduling, abort propagation |
| **TUI client state** (`tui-ttOZNpsl.js:2025-2641`) | Browser-side JavaScript in-memory | Whether TUI renders as "running"/"finishing context"/"idle"; whether `/new` and `/abort` are allowed |

The gateway runtime is the **true** authority — it knows which runs are actually executing. The TUI state is a **mirrored view** that should track the gateway faithfully via lifecycle events (`phase: "start" | "finishing" | "end" | "error"`).

**The bug**: The mirror becomes stale when lifecycle events from an aborted run are lost or superseded by a concurrent new run.

### 2.2 Where is the stale "active run" state stored?

Three TUI-side state fields (all in-memory, `tui-ttOZNpsl.js`):

```javascript
// Line 2641: activeChatRunId
if (state.activeChatRunId === acceptedRunId) state.activeChatRunId = null;

// Line 2025: pending states that also count toward the rollback guard
const hasTrackedAbortTarget = () => Boolean(
    state.activeChatRunId ||      // ← The stale field
    state.pendingChatRunId ||      // Pending run from /new
    state.pendingOptimisticUserMessage  // User message sent before server ack
);

// Line 2026: the gate function that blocks /new and /abort
const hasUnsafeSessionRollover = () => 
    hasTrackedAbortTarget() || 
    state.activityStatus === "finishing context";  // ← Also stale, no timeout

// Line 3454: where "finishing context" is set (no corresponding clear exists with a fallback)
setActivityStatus("finishing context");
```

**Critical finding**: `activityStatus === "finishing context"` is the **only** sentinel that has NO explicit clear path other than receiving an `phase === "end"` lifecycle event. It also feeds into `hasUnsafeSessionRollover()`, which means even if `activeChatRunId` were cleared, this field alone blocks `/new`.

### 2.3 Why does `run aborted` not clear the stale state?

Three independent failure modes in the gateway-side abort flow (`get-reply-OTG64ybi.js:3574-3579`, `runs-B0SQhu92.js:317-353`):

**Mode A — Abort completes but lifecycle event is lost:**
```
Gateway: embeddedAgentRuntime?.abortEmbeddedAgentRun(activeSessionId)
    → removes run from ACTIVE_EMBEDDED_RUNS
    → sets ABANDONED_EMBEDDED_RUNS_BY_SESSION_ID
    
But the TUI never receives phase:"error" or phase:"end" because:
1. The WebSocket/stream was closed before event delivery
2. Or the event arrived after a concurrent /new triggered a new run lifecycle
3. Or compaction failure corrupted session state (TASK_DS_EO_032 Bug 2, Mode #2)
```

**Mode B — Abort triggers compaction during abort recovery:**
```
User sends /abort → gateway clears command lane + aborts embedded run
    → TUI receives phase:"finishing" → sets activityStatus="finishing context"
    → compaction kicks in (mid-turn precheck detects overflow from prior turns)
    → compaction times out or fails (Mode #2: post-abort state corruption)
    → error event never delivered; session left in "finishing context" forever
```

**Mode C — Gateway-side abort races with send completion:**
```
TUI sends user message → gateway starts new run
    → TUI sets activeChatRunId = <new_run_id>
    → Meanwhile old run's phase:"error" arrives (from prior abort)
    → hasConcurrentActiveRun(new_error.runId) returns true ← blocks cleanup
    → error event for old run is silently dropped
    → activeChatRunId still points to <new_run_id> which may have also completed
```

### 2.4 Why can `/abort` not reconcile the stale state when runtime says no active run?

Look at the abort handler (`tui-ttOZNpsl.js:2538-2541`):

```javascript
case "abort":
    await abortActive();  // ← calls client-side abort, NOT a guard check
    break;
```

The `/abort` command does **not** first check `hasUnsafeSessionRollover()`. It unconditionally calls `abortActive()`, which sends a request to the gateway. The gateway's side (`get-reply-OTG64ybi.js:3574`) checks if there's an active run and aborts it — but if none exists, **it silently succeeds** (aborted = false/undefined).

The TUI then waits for lifecycle events to update its state. If those events are lost (as shown above), `activeChatRunId` remains stale. But here's the deeper problem: **after a silent-success abort, no new lifecycle events fire**. The gateway has nothing to report because there was no run to report on.

So the sequence becomes:
1. TUI thinks active run exists → sends `/abort` request
2. Gateway says "nothing to abort" (silent success)
3. No lifecycle event fires → TUI state doesn't change
4. TUI still thinks active run exists → loops back to step 1 on next attempt

### 2.5 Why can `/new` not recover from this condition?

`/new` has a hard gate at `tui-ttOZNpsl.js:2498`:

```javascript
case "new":
    if (hasUnsafeSessionRollover()) {  // ← returns true when stale
        chatLog.addSystem("abort the current run before /new");
        tui.requestRender();
        break;  // ← BLOCKED. Session never created. Forever.
    }
    sessionCreationInFlight = true;
```

`hasUnsafeSessionRollover()` at line 2026:
```javascript
const hasUnsafeSessionRollover = () => 
    hasTrackedAbortTarget() || state.activityStatus === "finishing context";
// hasTrackedAbortTarget() checks activeChatRunId, pendingChatRunId, pendingOptimisticUserMessage
```

**The deadlock**: To clear the stale state, we need `/abort` to fire a lifecycle event. But lifecycle events may never come (silent success abort). And `/new` is blocked by the very stale state we need to clear. It's a **self-reinforcing deadlock**.

### 2.6 Is this related to TASK_DS_EO_032/033?

**Yes, directly and indirectly.** Both investigations identified overlapping bugs:

| Bug | TASK_DS_EO_032 (Run Abort State Sync) | TASK_DS_EO_039 (This investigation) |
|-----|--------------------------------------|-------------------------------------|
| **Bug 2: TUI stuck after abort** | Confirmed race between compaction and abort lifecycle events (tui-ttOZNpsl.js:3443-3444). `hasConcurrentActiveRun()` blocks old lifecycle events since `activeChatRunId` now points to NEW run. Stale "finishing context" state never clears. | **Confirmed.** The same race condition at line 3444 is the primary driver. Confirmed by source code analysis of `handleChatEvent`. |
| **Bug: Mode #2 compaction failure** | Orphaned session artifacts from prior abort cause `serializeConversation()` to produce malformed output, hanging summarization LLM. Compaction fails even at low context. | **Confirmed.** Post-abort state corruption in gateway-side abandoned-run maps contaminates subsequent session operations. |
| **Token display (262k / 986%)** | Not a bug — accumulated turn cost across many tool-use rounds (proxy-BzhBz8iM.js:2146). | Same finding confirmed. Correlates with this failure mode because long tool-use sessions accumulate enough turns to trigger mid-turn precheck during the abort recovery window. |
| **`scheduleTerminalLifecycleError`** | Should emit TUI lifecycle error events on failure, not throw exceptions (proxy-BzhBz8iM.js:2384). Abort handler must flush orphaned session artifacts before clearing activeChatRunId. | **Confirmed.** `abortActiveReplyRuns()` (run-state-BteeOQT8.js:545) sets abort flags but doesn't emit lifecycle events to TUI on success-with-nothing-to-abort. |

**The gap TASK_DS_EO_039 closes**: TASK_DS_EO_032 identified the race condition and Mode #2 compaction failure. It did NOT investigate why `/new` cannot recover (it only noted "/new or /reset required"). TASK_DS_EO_039 traces the full deadlock chain from gateway abort → stale TUI state → blocked recovery commands.

### 2.7 Can a reconciliation/forced-cleanup path safely recover without Ctrl+C?

**Yes, and several candidate paths exist:**

#### Path A: Client-side forced-clear (most robust, client-initiated)
Add a `/resetrun` command that bypasses the `hasUnsafeSessionRollover()` gate:
```javascript
// In tui-ttOZNpsl.js handleCommand:
case "resetrun":
    state.activeChatRunId = null;
    state.pendingChatRunId = null;
    state.pendingOptimisticUserMessage = false;
    state.activityStatus = "idle";
    // Clear abandoned run maps on server side via client API
    await client.resetSession(state.currentSessionKey);
    chatLog.addSystem("Run state reset. Session ready.");
    tui.requestRender();
    break;
```

#### Path B: Abort with forced event (gateway-side fix)
In `get-reply-OTG64ybi.js` after the abort succeeds with no active run:
```javascript
// Current (line 3578): just logs
if (!aborted) { /* nothing happens */ }

// Should add: if TUI had an activeChatRunId for this session, 
// emit a phase:"end" event to clear the TUI state.
if (!aborted && wasActiveSessionForCurrentTUI(sessionKey)) {
    // Emit lifecycle event to TUI: phase:"end", status:"idle"
    emitTerminalLifecycleEvent(sessionKey, "end");
}
```

#### Path C: `activityStatus === "finishing context"` timeout (defense in depth)
Add a watchdog timer that clears "finishing context" after 60s of inactivity:
```javascript
// In tui-ttOZNpsl.js handleChatEvent:
if (phase === "finishing") {
    clearTimeout(staleFinishingTimer);
    staleFinishingTimer = setTimeout(() => {
        if (state.activityStatus === "finishing context" && 
            !state.activeChatRunId && 
            sessionRuns.size === 0) {
            setActivityStatus("idle");
            chatLog.addSystem("Stale finishing state cleared after timeout.");
        }
    }, 60000);
}
```

#### Path D: `hasUnsafeSessionRollover()` relaxation for `/reset`
The `/reset` command (unlike `/new`) currently does NOT check `hasUnsafeSessionRollover()`. If the user uses `/reset` instead of `/abort`, it resets the session which clears all abandoned runs on the server side and should clear TUI state. The issue is that users instinctively try `/abort` first, getting stuck.

**Recommendation**: Priority order for fixes:
1. **Path B (gateway-side)** — Fix the root cause: abort-with-nothing should emit lifecycle events
2. **Path C (defensive timeout)** — Add stale "finishing context" cleanup as defense-in-depth
3. **Path A (client workaround)** — Add `/resetrun` for immediate user relief

---

## 3. Run State Reconciliation Requirements

### 3.1 Required invariant

> The system MUST maintain the following invariants at all times:
> - If `gateway ACTIVE_EMBEDDED_RUNS.size === 0`, then TUI `activityStatus` MUST NOT be `"finishing context"` or `"running"` for more than 5 seconds without an intervening lifecycle event.
> - If TUI `activeChatRunId` is non-null but the corresponding run is not in gateway's active registry, the TUI MUST clear it within 10 seconds of detecting the inconsistency (no external intervention required).
> - `/abort` and `/new` MUST NEVER be simultaneously blocked when no actual run is executing.

### 3.2 State synchronization map

| Layer | State Variable | Authoritative? | Stale-by-default timeout |
|-------|---------------|----------------|--------------------------|
| Gateway runtime | `ACTIVE_EMBEDDED_RUNS` (Map) | Yes (true authority) | N/A — server owns lifecycle |
| TUI client | `activeChatRunId` (string/null) | No — mirror only | 10s without lifecycle event → auto-clear |
| TUI client | `activityStatus` ("idle"/"running"/"finishing context") | No — mirror only | "finishing context" must have 60s timeout |
| Gateway abandoned | `ABANDONED_EMBEDDED_RUNS_BY_SESSION_ID` (Map) | Yes (source of truth for completed/abandoned) | Pruned on next `/abort` or session reset |

### 3.3 Event delivery requirements

- **Every abort MUST produce at least one lifecycle event** delivered to the TUI, even if no run was found to abort (status: "idle" with message).
- **Lifecycle events must be sequenced**: `phase:"finishing"` must be followed by `phase:"end"` or `phase:"error"` — never left hanging.
- **The gateway MUST not silence a successful-but-nothing-to-abort case** — it must produce a terminal event to the TUI that clears mirrored state.

---

## 4. Token Accounting Correlation

### 4.1 Observed display values

```
tokens 570k/262k (217%)
tokens ~999k/262k (381%)
```

### 4.2 Root cause (confirmed in TASK_DS_EO_032)

This is **not** context overflow. The TUI's "used" value is the cumulative sum of provider-reported usage from the last assistant message plus all trailing token estimates across subsequent messages (`estimateContextTokens(messages)` in proxy-BzhBz8iM.js:2146). During long tool-use loops with hundreds of tool calls, each turn adds its own input+output+tool-overhead costs.

### 4.3 Correlation with this failure mode

Long tool-use sessions are the **primary trigger** for this deadlock because:
1. They accumulate enough turns to hit mid-turn precheck overflow thresholds (reserves ~48K tokens floor, effective window ~214K tokens)
2. When overflow triggers during an active run, compaction fires — which runs on the same model that's being called → increased load → longer inference times
3. The abort handler clears the command lane and starts a new embedded run to handle the `/abort` request — this NEW run competes for the same Ollama instance
4. The TUI receives `phase:"finishing"` from compaction start, then may lose the subsequent `phase:"error"` from compaction timeout or get `phase:"end"` from the abort's new run before the old error arrives (TOCTOU)

The high token display is a **symptom**, not a cause. But it correlates because it indicates the session reached the overflow threshold that triggers compaction, which is the most common entry point for this deadlock chain.

---

## 5. Complete Failure Chain

```
┌─────────────────────────────────────────────────────────────────┐
│ Session accumulates hundreds of tool-use turns (long CTO work) │
│ TUI display: "tokens 570k/262k (217%)" — cumulative cost      │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ Mid-turn precheck detects overflow → triggers                    │
│ contextEngine.compact() via embedded run on SAME Ollama model   │
│ (ollama/qwen3.6:35b, CPU-only Tegra hardware)                   │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ Compaction takes > compaction.timeoutSeconds (300s in our config)│
│ Gateway aborts compaction → TUI receives:                       │
│   - phase:"finishing" → activityStatus="finishing context"      │
│   - compaction error (no lifecycle event for the abort!)        │
│   → "finishing context" has NO timeout or forced-clear          │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ User hits /abort to cancel stuck compaction                     │
│ Gateway: abortEmbeddedAgentRun() → nothing found (already done) │
│   → silent success, NO lifecycle event emitted                  │
│ TUI: still has activeChatRunId + activityStatus="finishing"     │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ User hits /abort again → gateway silently succeeds again        │
│ User hits /new → BLOCKED by hasUnsafeSessionRollover()          │
│   ← same stale state blocks recovery                            │
│                                                                 │
│ DEADLOCK: no command can clear the stale state                  │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│ Only solution: Ctrl+C → restart OpenClaw → new session          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Fix Recommendations

### Priority 1 — Gateway-side (root cause)
**File**: `get-reply-OTG64ybi.js` or equivalent gateway reply handler

When `abortEmbeddedAgentRun()` returns false/undefined (no active run found), emit a terminal lifecycle event to the TUI with `phase:"end", status:"idle"` to clear mirrored state. This ensures the abort path always produces at least one event that the TUI can process.

### Priority 2 — Defensive timeout
**File**: `tui-ttOZNpsl.js`

Add a 60-second watchdog timer on `activityStatus === "finishing context"` that auto-clears to `"idle"` when no active run is detected. This prevents permanent stale states even if lifecycle events are lost.

### Priority 3 — Client-side workaround
**File**: `tui-ttOZNpsl.js` or user documentation

Add `/resetrun` command (or allow `/abort` to force-clear on second invocation with a "forcing" flag) that bypasses the `hasUnsafeSessionRollover()` gate when runtime says no active run.

### Priority 4 — Post-compact cleanup
**File**: `run-state-BteeOQT8.js`, `runs-B0SQhu92.js`

After compaction failure, ensure abandoned run state is fully cleaned up from gateway-side maps (`ABANDONED_EMBEDDED_RUNS_BY_SESSION_ID`, etc.) and a clear event fires to TUI.

---

## 7. Predecessor Task Correlation Matrix

| TASK | Finding | Relationship to This Investigation |
|------|---------|-------------------------------------|
| **TASK_DS_EO_032** (run abort state sync) | Bug 2: TUI stuck after abort; race at line 3444. Mode #2 compaction failure. Token display not a bug. | **Direct predecessor.** This investigation expands the analysis to include the full deadlock chain from gateway-side abort → TUI stale state → blocked recovery commands. TASK_DS_EO_032 identified the race and Mode #2 but did not trace why `/new` is blocked (it only noted the workaround). |
| **TASK_DS_EO_033** (cross-role compaction) | Compaction timeouts at exactly 120s (now 300s), CPU-only hardware, same-model compaction. | **Contributing factor.** The long compaction timeout is what triggers the abort-and-stuck state in the first place. Longer timeout (300s applied) reduces frequency but doesn't eliminate it. |

---

## 8. Testing Strategy for Fix Validation

To verify any fix works:

1. Run a long CTO session with many tool calls (100+ to trigger overflow)
2. Let mid-turn compaction trigger during active work
3. Hit `/abort` immediately after seeing "finishing context"
4. Verify: TUI shows "idle", `/new` works, no Ctrl+C required
5. Run the same scenario 10 times (the race is probabilistic)

---

*Investigation complete. Pending CTO planning for fix implementation.*
