---
produced_by: ollama/qwen3.6:35b
session_id: 16bb6db9-dac0-4551-b9fb-7cff8402ede9
produced_at: 2026-08-08T13:06:00-07:00
role: CTO
task_id: TASK_20260808_032
gate: G1
---

# CTO Plan — Investigation of Run Abort State Sync and Token Accounting Bugs

## Problem Statement

Evidence from user observation shows two related OpenClaw bugs during a stuck run:

1. **Compaction/summarization becoming stuck or timing out** when processing large sessions (known issue, partially understood)
2. **TUI session state failing to synchronize after run abort**, continuing to display "running" despite the backend reporting "no active run" / "run aborted"

Additionally, the displayed context usage `2.6m/262k (986%)` needs analysis: is this genuine accumulated transcript size, a token-accounting bug, or both?

## Scope

Investigate and document root causes for:
- **Bug 1**: Token accounting producing percentages >100%
- **Bug 2**: TUI run state becoming out-of-sync after abort/error
- **Relationship**: Determine if the compaction timeout triggers a race condition in the TUI state machine

## Investigation Approach

### Phase 1: Trace token accounting for "2.6m/262k (986%)"

Source files to inspect:
- `proxy-BzhBz8iM.js`: `calculateContextTokens()`, `estimateContextTokens()`, `getLastAssistantUsage()`
- `tui-ttOZNpsl.js` + `control-ui/assets/chat-page-DrPkxqJK.js`: how the TUI computes and displays context percentage
- `embedded-agent-DGUuxGR2.js`: how usage data flows from the run to the session state

Key question: Does `contextTokens` (current context window size) get accumulated across turns, or does it report a single-turn cost? The formula at line 2161-2165:
```js
const usageTokens = calculateContextTokens(usageInfo.usage);
let trailingTokens = 0;
for (let i = usageInfo.index + 1; i < messages.length; i++) trailingTokens += estimateTokens(messages[i]);
return { tokens: usageTokens + trailingTokens, ... };
```

If `estimateContextTokens` is called on the full session message list, the "trailing tokens" could accumulate massively during a long multi-turn tool-use loop. The "used" value would be the sum of all input/output tokens across the entire session (not just current context window), leading to >100%.

### Phase 2: Trace TUI state synchronization after abort

Source files to inspect:
- `tui-ttOZNpsl.js`: lifecycle event handlers, specifically the `handleAgentEvent` function around lines 3437-3480
- Key race condition check: the `canUpdateActivityStatus = !hasConcurrentActiveRun(evt.runId)` guard at line 3444
- The `finishing` → `error`/`end` phase sequence during compaction timeout

Key question: Does a lifecycle event arrive for an already-aborted runId and get silently dropped because of the concurrent active run check?

### Phase 3: Determine compaction error propagation path

Source files to inspect:
- `proxy-BzhBz8iM.js`: `runSummarizationCompletion()` at line 2385 — how abort errors map to CompactionError
- How compaction errors propagate through the agent run lifecycle in `embedded-agent-DGUuxGR2.js`
- Whether a failed compaction causes the run to return with `aborted: true` while the TUI hasn't yet received the `error`/`end` lifecycle event

### Phase 4: Cross-reference and correlate findings

Determine whether the high token count and the state sync issue are causally related (e.g., compaction triggers a late error path that races with TUI state updates) or independent.

## Deliverables

1. `INVESTIGATION.md` — full root cause analysis with evidence citations
2. Recommendations for fixes: either OpenClaw-level patches to report, or DS-EO-level workarounds/configs

## Acceptance Criteria

- Clear explanation of how each observed value (2.6m/262k, >100%, "running" after abort) is produced
- Identification of the exact code path(s) responsible for each bug
- Evidence that either confirms or rejects hypotheses about causal relationships between the two bugs
