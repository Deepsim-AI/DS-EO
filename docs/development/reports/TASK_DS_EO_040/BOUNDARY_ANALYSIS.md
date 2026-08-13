# TASK_DS_EO_040 — Boundary Analysis

**Date:** 2026-08-12  
**Task ID:** TASK_DS_EO_040  
**Phase:** G2 (Implementation) — Pre-implementation deliverable  
**Source:** Inspected OpenClaw v2026.7.1-2 dist bundles on host deepsim

---

## 1. Methodology

Inspected the following OpenClub dist modules to determine what APIs are available at runtime, what state is managed internally, and which fixes belong in DS-EO vs. upstream OpenClaw core:

| Module | Path (OpenClaw dist) | Responsibility |
|--------|---------------------|----------------|
| `run-state-BteeOQT8.js` | Run state registry (reply/run lifecycle) |
| `abort-J462pIQw.js` | `/abort` command handler |
| `abort-primitives-Eo9j6lAM.js` | Abort primitives/utilities |
| `runs-B0SQhu92.js` | Embedded agent run management (queue, abortability) |
| `session-accessor-D7yi6P1i.js` | Session entry persistence, abort target resolution |
| `dispatch-DnzGTpPs.js` | Command dispatch, run state propagation |
| `agent-runner.runtime-DtdxZiBX.js` | Agent runner lifecycle, event bridges |
| `cli-runner-DE2P2Dy_.js` | CLI agent execution (`runCliAgent`, `runPreparedCliAgent`) |
| `embedded-agent-DGUuxGR2.js` | Embedded agent session management, compaction |
| `errors-XbAR6hS3.js` / `errors-sMD712F3.js` | Error classification (`detectErrorKind`, `classifyFailoverReason`) |
| `sessions*.js` (multiple) | Session resolution, key mapping, cleanup |
| `agent-command-ABV9I5el.js` | Agent command runtime, session reset persistence |
| `acp-reset-target-BavR4Si3.js` | Reset target session key resolution |

---

## 2. Findings — What OpenClaw Exposes at Runtime

### 2.1 Available APIs (no source modification needed)

| API / Function | Module | Can DS-EO Call? |
|----------------|--------|-----------------|
| `replyRunRegistry.isActive(key)` | run-state | Yes — via session tool (`sessions_list` with active filter, or gateway IPC if available) |
| `replyRunRegistry.abort(key)` | run-state | **No** — internal registry only; exposed via `/abort` command |
| `resolveActiveEmbeddedRunSessionId(key)` | run-state | **No** — internal helper, not exported as public API |
| `loadSessionEntry(scope)` | session-accessor | **Partially** — via gateway/session tools (read-only session state) |
| `listSubagentRunsForController(key)` | subagent-registry | **Partially** — via `sessions_list` tool |
| `abortEmbeddedAgentRun(sessionId)` | runs | **No** — internal; only accessible via `/abort` command handler |
| `detectErrorKind(err)` | errors-sMD712F3.js | **No** — internal TypeScript function, not exposed as runtime API |
| `classifyFailoverReason(msg, opts)` | errors-XbAR6hS3.js | **No** — internal, provider-specific classifier |
| `formatErrorMessage(err)` | errors-sMD712F3.js | **No** — internal formatter |
| `isCompactionFailureError(errorMessage)` | errors-XbAR6hS3.js | **Partially** — pattern detection possible from error message text |
| `isContextOverflowError(errorMessage)` | errors-XbAR6hS3.js | **Partially** — pattern detection possible from error message text |

### 2.2 Internal State (NOT exposed via public APIs)

| State Element | Location | Exposed? | Notes |
|--------------|----------|----------|-------|
| `activeRun` / `replyRunState.activeKeysBySessionId` | run-state-BteeOQT8.js | **No** | In-memory WeakMap/Symbol singleton; no getter exposed to runtime tools |
| `runId` on replyPayload | dispatch-DnzGTpPs.js:2532-2554 | Partially | Available in tool output but not as a queryable state field |
| Run lifecycle phase (STARTING/ACTIVE/COMPLETED/etc.) | agent-runner.runtime-DtdxZiBX.js:260+ | **No** | Transient; no status API exists |
| `replyRunRegistry._abort()` internal state | run-state-BteeOQT8.js | **No** | Internal method only |
| Session transcript lifecycle (compaction checkpoints) | sessions-compact-CkevFtdS.js | Partially | Via session_status tool but not raw checkpoint data |

### 2.3 Key Discovery: No `active_run` State Query API Exists

OpenClaw has **no public runtime API** that answers "is there an active run for this session?" The state is:
- Maintained in `replyRunState.activeKeysBySessionId` (in-memory Symbol registry)
- Never exposed via `/run`, session_status, or any tool output as a boolean field
- Only inferable indirectly from error messages ("no active run", "agent running")

This is the **root cause** of the "impossible state" — the control plane has no way to probe engine reality.

---

## 3. Requirement-by-Requirement Boundary Classification

### N1-1: Run State Reconciliation

**Classification: HYBRID (upstream patch needed + DS-EO workaround)**

| Aspect | Location | Details |
|--------|----------|---------|
| **DS-EO work** | DS-EO agent protocol layer | Agent-facing state inference from available tools (session_status, sessions_list). Can detect `no active run` error messages and classify them. |
| **Upstream need** | OpenClaw core — add `resolveActiveRunState()` API | The engine's `activeRun` state in `run-state-BteeOQT8.js:9` is not accessible at runtime. Requires adding a getter function exported to the tool layer. |

**Specific upstream fix needed:**
- **File:** `openclaw/dist/run-state-BteeOQT8.js` (or source equivalent)
- **Function to add:** `function resolveActiveRunState(sessionKey: string): { isActive: boolean, runId?: string, phase: 'idle'|'starting'|'active'|'aborted'|'unknown' }`
- **Where:** After the existing `resolveReplyRunForCurrentSessionId` function (~line 46)
- **Dependency:** `replyRunRegistry.isActive(key)` is already available; need to wrap it as a publicly accessible function

### N1-2: Explicit Run Lifecycle States

**Classification: DS-EO-only (protocol specification)**

The state model can be fully defined at the protocol/agent level without upstream changes. The states (IDLE → STARTING → ACTIVE → COMPLETED/FAILED/ABORTED/TIMEOUT) are DS-EO's classification layer over whatever the engine reports.

- **DS-EO deliverable:** State machine spec, transition rules, and agent instructions
- **Upstream:** No code change needed; upstream could optionally align its internal state names but that's cosmetic

### N1-3: Structured Error Classification

**Classification: DS-EO-only (interceptor pattern)**

OpenClaw already has `detectErrorKind(err)` in `errors-sMD712F3.js` which classifies:
- `"refusal"`, `"rate_limit"`, `"timeout"`, `"context_length"`

However, it returns `undefined` for unclassified errors — which is exactly where `run error: unknown` falls.

| Aspect | Location | Details |
|--------|----------|---------|
| **DS-EO work** | DS-EO error classification layer | Intercept raw error messages, apply DS-EO's own mapping: `RUN_STATE_MISMATCH`, `ORPHANED_RUN`, `COMPACTION_ABORT_FAILURE`, `RETRYABLE_ERROR`, `IRRECOVERABLE_ERROR` |
| **Upstream benefit** | Could integrate DS-EO codes upstream | The `detectErrorKind` function in `errors-sMD712F3.js:94-102` is the natural place for upstream to adopt broader classification |

**DS-EO interceptor approach:** Error messages are available as tool output. An agent-facing error mapper can parse message patterns:
- `"no active run"` + control-plane shows active → `RUN_STATE_MISMATCH`
- `"Agent reply is already finalizing"` + abort attempted → `ABORT_DURING_FINALIZATION`
- Compaction failure patterns from `errors-XbAR6hS3.js:207-221` → `COMPACTION_ABORT_FAILURE`

### N1-4: Abort Cleanup Recovery

**Classification: HYBRID (upstream `/abort` fix + DS-EO protocol)**

| Aspect | Location | Details |
|--------|----------|---------|
| **Upstream need** | OpenClaw core — `/abort` command handler | `abort-J462pIQw.js:36` calls `replyRunRegistry.isActive(key)` and `replyRunRegistry.abort(key)` internally. When these return inconsistent results (active=true but abort=false), the abort silently fails without cleanup state. Needs explicit reconciliation logic in `abortSessionRunTargetWithOutcome()`. |
| **DS-EO work** | Agent recovery protocol | When upstream `/abort` leaves stale state, DS-EO agents use manual session reset procedures (clearing session entry via gateway tools) as fallback |

**Specific upstream fix:**
- **File:** `openclaw/dist/abort-J462pIQw.js`  
- **Function:** `abortSessionRunTargetWithOutcome()` (~line 36)
- **Issue:** Returns `{active, aborted}` but doesn't handle the case where `active=true && aborted=false` — should transition control-plane to IDLE state automatically
- **Also:** `resolveStoredSessionId()` at line 59 reads session entry for abort target lookup; when this fails (corrupted session), abort silently does nothing

### N1-5: New Run Recovery

**Classification: HYBRID (upstream `/new` fix + DS-EO protocol)**

| Aspect | Location | Details |
|--------|----------|---------|
| **Upstream need** | OpenClaw core — run bootstrapping | `dispatch-DnzGTpPs.js:2552-2554` sets `runState.runId = runId` on agent run start. When this conflicts with stale session entry state, no reconciliation happens. The reset path in `acp-reset-target-BavR4Si3.js:43` (`resolveEffectiveResetTargetSessionKey`) doesn't validate against current run state. |
| **DS-EO work** | Agent recovery protocol | DS-EO agents can use gateway session tools to manually reset (create new session) when `/new` fails |

**Specific upstream fixes:**
1. **File:** `openclaw/dist/dispatch-DnzGTpPs.js`  
   **Function:** `bindReplyPayloadRunState()` (~line 2552)  
   **Issue:** Sets runId without validating that no stale run was previously active
2. **File:** `openclaw/dist/acp-reset-target-BavR4Si3.js`  
   **Function:** `resolveEffectiveResetTargetSessionKey()` (~line 43)  
   **Issue:** Doesn't check current engine state before setting reset target

### N1-6: Stale/Orphaned Run Detection

**Classification: DS-EO-only (detectable via available APIs)**

This is the most DS-EO-recoverable requirement. Detection can be done by:

1. Querying session state via `sessions_list` with active filter
2. Checking for "no active run" error messages during dispatch
3. Comparing control-plane session status against agent runner output in `agent-runner.runtime-DtdxZiBX.js:308-333` (the event bridge checks `evt.runId !== params.runId`)

**DS-EO implementation:** The reconciliation loop polls available state via gateway tools or event bridges. No upstream API change needed — just agent logic that knows what patterns to look for.

### N1-7: Recovery without Restart

**Classification: HYBRID (upstream patch + DS-EO protocol)**

| Aspect | Location | Details |
|--------|----------|---------|
| **Upstream need** | OpenClaw core — `/new` bootstrap path | When `dispatch-DnzGTpPs.js:1798` creates a new runId (`crypto.randomUUID()`), it doesn't clean up any stale session entry from the previous failed run. The orphan persists in `persistSessionEntry$1()` (agent-command-ABV9I5el.js:335). |
| **DS-EO work** | Agent recovery procedures | Manual steps for agents when automated recovery fails: clear session entry, create new session via gateway API |

---

## 4. Summary Matrix

| N1 Requirement | DS-EO-only | Upstream-needed | Hybrid Components |
|---------------|------------|-----------------|-------------------|
| N1-1 Run State Reconciliation | Agent-facing state inference from tools | `resolveActiveRunState()` API in run-state | Detection logic (DS-EO) + state query API (upstream) |
| N1-2 Explicit Lifecycle States | ✅ Fully DS-EO (protocol spec only) | — | None needed |
| N1-3 Structured Error Classification | ✅ Fully DS-EO (error interceptor) | Optional: extend `detectErrorKind()` upstream | None needed; upstream could benefit but not required |
| N1-4 Abort Cleanup Recovery | Agent recovery protocol when `/abort` leaves stale state | Fix `abortSessionRunTargetWithOutcome()` reconciliation in abort-J462pIQw.js | Error handling (DS-EO) + abort flow fix (upstream) |
| N1-5 New Run Recovery | Agent recovery protocol for `/new` failures | Fix runId bootstrapping validation in dispatch-DnzGTpPs.js:2552 | Reset logic (DS-EO) + state validation (upstream) |
| N1-6 Orphan Detection | ✅ Fully DS-EO (poll available APIs) | None needed — already detectable | None |
| N1-7 Recovery without Restart | Agent recovery procedures | Fix runId cleanup in dispatch-DnzGTpPs.js:1798 | Cleanup logic (upstream) + fallback procedures (DS-EO) |

**Totals:**
- Fully DS-EO-only: **3/7** (N1-2, N1-3, N1-6)
- Hybrid (needs upstream): **4/7** (N1-1, N1-4, N1-5, N1-7)
- Upstream-only: **0/7** (all hybrid requirements have DS-EO components too)

---

## 5. Implementation Plan — Phased Approach

### Phase 1: DS-EO Layer (Can proceed immediately, no upstream dependency)

| # | Deliverable | Type | Priority |
|---|------------|------|----------|
| P1-1 | `reconciler.py` with `classify_error()` and `detect_orphaned_runs()` | DS-EO code | P0 — fully DS-EO recoverable |
| P1-2 | Agent recovery protocol document (manual procedures for each failure mode) | Protocol spec | P0 — works now even without upstream |
| P1-3 | Error classifier mappings (raw message → structured code) | Protocol + code | P0 — DS-EO-only requirement N1-3 |
| P1-4 | Integration tests T1-T5 (mocked, no real OpenClaw runtime needed) | Tests | P0 |

### Phase 2: Upstream Patch Proposals (Track as blocking dependencies)

| # | What to patch | File/Location | Effort Estimate |
|---|--------------|---------------|-----------------|
| U1 | Add `resolveActiveRunState()` public API | run-state-BteeOQT8.js (~line 46, after resolveReplyRunForCurrentSessionId) | Low — 20 lines, uses existing `replyRunRegistry.isActive()` |
| U2 | Fix abort reconciliation in `abortSessionRunTargetWithOutcome` | abort-J462pIQw.js:36-55 | Medium — needs careful state cleanup logic |
| U3 | Validate runId during new run bootstrap | dispatch-DnzGTpPs.js:1798, 2552-2554 | Medium — needs stale state detection |
| U4 | Clean up stale session entry on `/new` success | agent-command-ABV9I5el.js:335 (`persistSessionEntry$1`) | Low — add cleanup call before persistence |

### Phase 3: Integration (After upstream patches land)

| # | Deliverable | Notes |
|---|------------|-------|
| P3-1 | Replace DS-EO workarounds with real API calls | Once U1 lands, replace tool-based probing with `resolveActiveRunState()` |
| P3-2 | End-to-end recovery testing on live sessions | Validate that desync scenarios are fully resolved |
| P3-3 | Update agent recovery protocol to use automated recovery | Manual procedures become fallback only |

---

## 6. Risk Assessment for Boundary Classification

### Risk: Upstream patch timeline unknown

**Mitigation:** Phase 1 is fully self-contained in DS-EO. All agent-facing error classification and manual recovery protocols work today with existing APIs. The DS-EO layer will use tool-based probing (sessions_list, session_status) as the detection mechanism until upstream API U1 lands.

### Risk: DS-EO reconciliation logic may conflict with upstream state machine

**Mitigation:** DS-EO's state model is a *classification layer* over runtime truth (N1-2 Principle: "When in doubt, trust the run engine"). DS-EO never writes to OpenClaw internal state — it only reads and classifies. When DS-EO detects a mismatch, it produces instructions; it doesn't attempt to fix state directly.

### Risk: Error classification patterns may evolve with OpenClaw updates

**Mitigation:** The error mapper in P1-3 uses message-pattern matching (regex) rather than exact string comparison. This makes it resilient to minor message formatting changes. Document the expected patterns and update when detected.

---

## 7. Acceptance Criteria Mapping

| AC | How It's Satisfied | Depends On |
|----|-------------------|------------|
| AC-1 | ✅ This document IS the BOUNDARY_ANALYSIS deliverable | — |
| AC-2 | `detect_orphaned_runs()` uses available tools (sessions_list, session_status) to probe run state | Phase 1 (DS-EO-only) |
| AC-3 | `classify_error()` maps raw messages using pattern matching + state context | Phase 1 (DS-EO-only) |
| AC-4 | Agent recovery protocol provides executable manual steps for each failure mode; automated path depends on upstream U2-U4 | Phase 1 (manual) / Phase 3 (automated) |
| AC-5 | Tests T1-T5 use mocked runtime state; pass without live OpenClaw runtime | Phase 1 (DS-EO-only) |
| AC-6 | Recovery instructions are explicit state → action mappings in agent protocol documents | Phase 1 (DS-EO-only) |
| AC-7 | State model, reconciliation mechanism, failure/recovery matrix all documented here and in CTO_PLAN.md | — |

---

**BOUNDARY_ANALYSIS COMPLETE.** All N1 requirements classified. Phase 1 can proceed immediately. Phase 2 upstream patches are tracked as dependencies for future work.
