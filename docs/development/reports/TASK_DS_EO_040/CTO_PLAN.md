# TASK_DS_EO_040 — Run Execution Reliability (N1)

**Plan Date:** 2026-08-12  
**Phase:** G1 (Planning)  
**Approver:** CTO  
**Status:** DRAFT — awaiting user approval  

---

## 1. Objective

Make OpenClaw runs recoverable when execution and control state diverge, so agents can continue working without manually restarting OpenClaw or pressing Ctrl+C.

**What we are building:** A run-state reconciliation and recovery layer that detects and corrects the desync between:
- Actual runtime run state (what OpenClaw's engine actually thinks is running)
- TUI/control plane run state (what the control UI / `/abort` / `/new` commands see)
- Agent/session state (what agents perceive their run context to be)

**What we are NOT building:** Another monitoring subsystem. N1 is about *recovery*, not observability. Session health observability (TASK_DS_EO_030) is separate and already scoped out per user directive.

---

## 2. Problem Statement

### Current Failure Modes

1. **`runtime = no active run` + `TUI/control = active run`** — The "impossible state." Runtime engine has lost the run, but the control plane still believes a run is active. Subsequent `/new` or agent-initiated commands fail with `run error: unknown` or deadlocks because neither side will advance.

2. **Unusable `/abort` and `/new`** — These control-plane commands themselves break when desync occurs, leaving the session in an unrecoverable state until manual intervention (Ctrl+C + restart).

3. **`run error: unknown` classification gap** — Error messages are opaque. Agents have no structured way to diagnose what went wrong or whether recovery is possible.

4. **Stale/orphaned runs** — Runs that terminated abnormally leave stale control-plane state with no automatic cleanup path.

5. **Compaction/abort interaction failures** — When auto-compaction fails (context overflow), the abort flow doesn't reliably clean up, compounding desync.

### Root Cause Analysis (from prior investigation)

The desync arises because:
- The OpenClaw run engine has its own state machine for `active_run`, `current_run_id`, etc.
- The TUI/control plane maintains separate "run is active" flags
- These two state sources are not reconciled on every operation
- When one side transitions (e.g., runtime crash, compaction failure) the other never learns
- Neither side's error handling covers the cross-side inconsistency

---

## 3. Scope

### In Scope (N1 Minimum Viable)

| # | Requirement | Description |
|---|-------------|-------------|
| N1-1 | **Run State Reconciliation** | Detect when runtime and control-plane diverge; reconcile to consistent state |
| N1-2 | **Explicit Run Lifecycle States** | Define and enforce: `idle` → `starting` → `active` → `completed` / `failed` / `aborted` / `timeout`. No undefined intermediate states. |
| N1-3 | **Structured Error Classification** | Replace opaque `run error: unknown` with categorized errors: `RUN_STATE_MISMATCH`, `ORPHANED_RUN`, `COMPACTION_ABORT_FAILURE`, `RETRYABLE_ERROR`, `IRRECOVERABLE_ERROR`, etc. |
| N1-4 | **Abort Cleanup Recovery** | Safe `/abort` that works even when desync has occurred — must clean up stale state on both sides |
| N1-5 | **New Run Recovery** | Safe `/new` that can bootstrap a fresh run from any desynced state |
| N1-6 | **Stale/Orphaned Run Detection** | Periodic check (or trigger-on-access) for runs where control plane says "active" but runtime has no corresponding process/session |
| N1-7 | **Recovery without restart** | All recovery paths must work within the running session — no Ctrl+C, no OpenClaw restart required |

### Out of Scope (deferred to later tasks)

| # | Requirement | Why deferred |
|---|-------------|--------------|
| O1 | Session Health automation (auto-actions on health events) | Scoped to TASK_DS_EO_030, user explicitly deferred auto-actions |
| O2 | `sessions_spawn` permission wiring | Scoped to TASK_DS_EO_038 — separate gateway/IPC layer |
| O3 | Upstream OpenClaw source changes (unless required) | We assess first what DS-EO can fix vs what needs upstream. N1 may need upstream patches but we evaluate that as part of the plan |
| O4 | Full telemetry/dashboards | Observability belongs to TASK_DS_EO_030, not recovery |

---

## 4. State Model

### Run Lifecycle States (authoritative)

```
     ┌─────────┐
     │  IDLE   │ ← default state for any session
     └────┬────┘
          │ /run or agent-initiated start
     ┌────▼────┐
     │ STARTING│ ← timeout: configurable (e.g., 30s), exceed → RECOVERY_REQUIRED
     └────┬────┘
          │ run engine confirms active
     ┌────▼────┐
     │ ACTIVE  │ ← primary work state
     └────┬────┘
    ┌─────┼──────────┬──────────┬──────────┐
    ▼     ▼          ▼          ▼          ▼
  COMPLETED FAILED   ABORTED TIMEOUT ORPHAN_DETECTED
```

**State transitions must be atomic across both runtime and control-plane.** No transient state may persist beyond a reconciliation cycle.

### Authoritative Sources of Truth

| Layer | Authority | Location |
|-------|-----------|----------|
| Run engine state | **Definitive source** for whether a run is actually executing | OpenClaw internal `run_engine` module |
| Control plane (TUI) | **Definitive source** for user-facing run status | TUI session state |
| Durable task state | **Definitive source** for whether a task was committed/abandoned | DS-EO task directory artifacts + git |
| Agent session context | **Derived** — must reconcile to engine truth, never trust its own perception over engine state | Inference session memory |

### Reconciliation Principle

> When in doubt, trust the run engine. The control plane and agent sessions are clients that must conform to engine reality.

---

## 5. Failure/Recovery Matrix

| Runtime State | Control-Plane State | Diagnosis | Recovery Action |
|---------------|---------------------|-----------|-----------------|
| no active run | active (run-id set) | **ORPHANED_RUN** / STATE_MISMATCH | N1-4: abort cleanup → transition control-plane to IDLE → allow fresh `/new` |
| no active run | idle | OK (consistent) | Normal operation |
| active | active | OK (consistent) | Normal operation |
| active | idle | **ENGINE_AHEAD** | Detect via /run ping; sync control plane forward to ACTIVE |
| starting | active | **TIMEOUT_IN_PROGRESS** | Wait for engine to complete STARTING→ACTIVE; if exceeds threshold, treat as ORPHANED_RUN |
| any (unknown) | active but run-id doesn't exist in engine | **INVALID_RUN_ID** | Clear stale control-plane state, transition to IDLE |

---

## 6. Implementation Approach

### 6.1 DS-EO vs Upstream Boundary Assessment

Before implementation, we must classify each fix:

| Fix Category | Where it lives | Decision criteria |
|-------------|---------------|-------------------|
| Reconciliation loop (periodic check) | Could be DS-EO or upstream | If it requires reading internal engine state → likely needs upstream hook; if it uses available APIs (`/run` ping, session status) → DS-EO layer |
| Abort recovery logic | Likely upstream (`/abort` command handler) | If fix is in the abort command's error handling → upstream patch required |
| Error classification output | Could be either | If error messages are generated by OpenClaw core → upstream; if DS-EO can intercept and reclassify → DS-EO layer |
| Orphaned run detection | DS-EO recoverable | Can use existing APIs to probe engine state without modification |

**Pre-implementation gate:** Before any code is written, produce a `BOUNDARY_ANALYSIS.md` that maps every N1 requirement to DS-EO-only, upstream-needed, or hybrid. This prevents building an oversized DS-EO subsystem when fixes belong upstream.

### 6.2 Minimum First Pass — DS-EO Recoverable Layer

The first implementation pass should focus on what DS-EO can do today with existing APIs:

1. **Orphaned run detector** — a lightweight function that queries the engine for current run state and compares to control-plane state; runs on every command dispatch or periodically (e.g., every 30s when session is alive)
2. **State reconciliation function** — given the comparison result from (1), emit structured diagnosis + proposed recovery action
3. **Safe abort/recovery commands** — DS-EO agent-level handlers that execute the recovery path for each diagnosed state, written as explicit agent instructions (not just code) since agent behavior IS the recovery mechanism
4. **Structured error mapper** — interceptor that catches `run error: unknown` and other opaque messages, maps them to classified errors using the diagnosis from (2)

### 6.3 If Upstream Patches Are Required

For fixes in OpenClaw core (`/abort`, `/new`, run engine state machine):
- Document exact file/symbol/line ranges needed
- Provide patch-ready changes targeting upstream repo
- N1 tracks these as `UPSTREAM_PR_REQUIRED` sub-items
- DS-EO implementation proceeds with stubs/workarounds for upstream-dependent items

---

## 7. Test Requirements

### Unit Tests (DS-EO layer)

| # | Test | What it validates |
|---|------|-------------------|
| T1 | Orphan detection: engine=none, control=active → returns ORPHANED_RUN | Correct diagnosis of impossible state |
| T2 | State sync: engine=active, control=idle → syncs to ACTIVE | Control plane catches up to engine |
| T3 | Clean state: engine=none, control=idle → no action needed | No false positives |
| T4 | Error classification mapping: `run error: unknown` with active_run=false → RUN_STATE_MISMATCH | Structured output for agents |
| T5 | Abort recovery flow: orphaned state → cleanup → IDLE transition | Full recovery path works |

### Integration / Reproduction Tests (require real sessions or controlled mock)

| # | Test | What it reproduces |
|---|------|-------------------|
| T6 | `no active run` deadlock reproduction and recovery | Actual failure case from production |
| T7 | `/abort` during desync → cleanup succeeds | Abort usability under desync |
| T8 | `/new` after desync → fresh run boots correctly | Fresh-run bootstrapping from bad state |
| T9 | Compaction failure + abort interaction → no double-orphan | TASK_DS_EO_032/033 compaction scenario |

---

## 8. Acceptance Criteria (G4)

All of the following must be satisfied for G4 approval:

- [ ] **AC-1:** BOUNDARY_ANALYSIS.md exists and maps every N1 requirement to DS-EO-only / upstream-needed
- [ ] **AC-2:** Orphaned run detection works reliably via available APIs (T1, T3)
- [ ] **AC-3:** Structured error classification replaces opaque `run error: unknown` in all agent-facing paths
- [ ] **AC-4:** Agent can recover from `runtime=no active run / control=active` without restarting OpenClaw
- [ ] **AC-5:** All DS-EO tests pass (T1-T5, or documented upstream-blocked)
- [ ] **AC-6:** Recovery instructions are explicit and executable by agents in real sessions
- [ ] **AC-7:** Documentation covers: state model, reconciliation mechanism, failure/recovery matrix, integration points

---

## 9. File/Symbol Guidance (R-SI-2 Compliance)

| Change | Target Path(s) | Symbol/Function | Approx Line |
|--------|---------------|-----------------|-------------|
| Run state reconciliation module | `ds_eo_openclaw/run_reliability/reconciler.py` (new) | `check_run_state()`, `reconcile_states()`, `classify_error()` | New file ~200 lines |
| Orphan detector | Same as above | `detect_orphaned_runs()` | ~80 lines |
| Agent recovery instructions | AGENTS.md or agent-specific protocol files | Section on recovery procedures | N/A (documentation) |
| Boundary analysis | Task directory | BOUNDARY_ANALYSIS.md | N/A |
| Upstream patches (if needed) | OpenClaw core `tui/` and `run_engine/` modules | Specific file/symbol from source inspection | To be determined |

---

## 10. Dependencies on Prior Tasks

| Task | Relationship | Notes |
|------|-------------|-------|
| TASK_DS_EO_032 | Compaction failure mechanics documented | Use compaction abort failure patterns as recovery test cases (T9) |
| TASK_DS_EO_033 | Compaction/session recovery procedures | N1 recovery must not conflict with 033's compaction barriers |
| TASK_DS_EO_038 | Gateway/spawn wiring audit | Out of scope; ensure no overlap in fixes |
| TASK_DS_EO_039 | Run-state desync fix plan (CLOSED) | N1 builds on 039 findings but is broader — 039 was targeted bugfixes, N1 is the reliability layer |
| TASK_DS_EO_030 | Session health code exists unapproved | Keep as-is; evaluate reuse potential after N1 interfaces are defined |

---

## 11. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Fixes require upstream patches to OpenClaw core | Medium | BOUNDARY_ANALYSIS gates; DS-EO layer works with stubs until upstream PRs land |
| Reconciliation loop adds overhead to active sessions | Low | Lightweight polling (~30s intervals); agent-triggered on demand is primary mechanism |
| Agents misapply recovery instructions | Medium | Recovery steps are explicit state → action mappings; tested in controlled scenarios |
| New desync patterns emerge not covered by matrix | Medium | Matrix is living document; review after first production deployment cycle |

---

## 12. Non-Goals (Explicitly Excluded)

- ❌ Automatic health monitoring actions (TASK_DS_EO_030 scope)
- ❌ `sessions_spawn` / gateway permission fixes (TASK_DS_EO_038 scope)
- ❌ Full telemetry, dashboards, or alerting infrastructure
- ❌ Agent model improvements (this is an infrastructure fix, not an AI capability issue)
- ❌ Changing the OpenClaw core run engine architecture (we adapt to it, don't redesign it)

---

**This plan is DRAFT.** Implementation may only begin after user approval of this plan and subsequent G1 gate check.
