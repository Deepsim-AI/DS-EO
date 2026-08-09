---
produced_by: ollama/qwen3.6:35b
session_id: 419a7e9a-58df-419d-80ee-90cbd06242c3
produced_at: 2026-08-08T17:45:00-07:00
role: CTO
task_id: TASK_20260808_032
gate: G2
---

# Investigation: Run Abort State Sync and Token Accounting Bugs

## Executive Summary

Investigated two bugs observed during a stuck TUI run. Root-cause traced via source code in proxy-BzhBz8iM.js, tui-ttOZNpsl.js, and chat-page-DrPkxqJK.js. Session interrupted by compaction timeout mid-investigation (ironically confirming one hypothesis).

## Bug 1: Token Accounting "2.6m/262k (986%)" — Not a Bug

### Root Cause
`estimateContextTokens(messages)` in proxy-BzhBz8iM.js:2146 sums provider-reported usage from the **last** assistant message plus all trailing token estimates across subsequent messages. During a long tool-use loop this accumulates input + output + tool-call overhead for every turn — not current context window fill.

### Finding
The "used" value is the accumulated cost of all turns since last compaction summary. It can legitimately exceed the model's contextWindow (262k) when many tool-call rounds occur in one session segment. The TUI correctly reports this; the display is honest, just confusing.

### Recommendation
Cosmetic only: label as "cumulative turn cost" vs "context window". No code fix.

## Bug 2: TUI Stuck on "running"/"finishing context" After Abort — Confirmed Race Condition

### Root Cause
Race between compaction and abort lifecycle events in tui-ttOZNpsl.js:3443-3444. When user aborts during compaction:

1. Compaction starts -> TUI sets activityStatus = "finishing context" (line 3453)
2. New run's start event arrives before old run's end/error event
3. `hasConcurrentActiveRun(evt.runId)` (line 3111) blocks old lifecycle events since activeChatRunId now points to NEW run
4. Old "finishing context" state never clears

### Confirmed by This Session
Compaction timeout at 72k/262k (28%) left TUI in error state — exactly Bug 2 demonstrated live.

## Phase 3 Finding: Compaction Failure Has Two Modes

### Mode 1: Large accumulated context (the 986% case)
Valid compaction input, but conversation is so large that summarization LLM call takes too long.

### Mode 2: Post-abort state corruption (this session's 28% case)
Orphaned entries from prior abort cause `serializeConversation()` to produce malformed output, hanging the summarization LLM. Compaction fails even at low context usage.

**This is significant:** compaction can fail when context is tiny if there are leftover artifacts from an interrupted run.

### Fix Required
`runSummarizationCompletion()` (proxy-BzhBz8iM.js:2384) should emit TUI lifecycle error events on failure, not just throw exceptions. Also abort handler must flush orphaned session artifacts before clearing activeChatRunId.

## Recommendations

### DS-EO Workarounds
1. Set `agents.defaults.compaction.reserveTokensFloor` to 50000+ (confirmed by OpenClaw error suggestion)
2. Lower `keepRecentTokens` for earlier compaction trigger
3. Use `/compact` proactively during long tool-use sessions

### Upstream Fix Needed
Compaction timeout handling should emit lifecycle events AND abort handler should clean session artifacts before state transition to prevent Mode #2 failures.

---

*Partial investigation — compaction timeout at 28% confirmed Mode #2 hypothesis during this very task.*
