# CTO Plan — TASK_DS_EO_026

**Task ID**: TASK_DS_EO_026  
**Phase**: Infrastructure  
**Title**: Fix Dispatcher `spawn_agent()` Real OpenClaw Session Creation  
**Date**: 2026-08-05  
**CTO**: qwen3.6:35b (ollama)

---

## 1. Problem Statement

The DS-EO Dispatcher's `SessionDispatcher.spawn_agent()` path reports success but returns a **mock/stub** — it does not create a real OpenClaw agent session. This breaks the automatic model workflow entirely: when a task advances from S1_PLANNING to S2_IMPLEMENTATION, the Implementer is never actually instantiated, so work cannot proceed.

This defect was discovered during TASK_DAL_002 (Content Inventory + Information Architecture) when G2 could not dispatch because no real Implementer session existed despite the dispatcher claiming success.

## 2. Current State Analysis

### 2.1 What Exists (Working Components)

| Component | Status | Location |
|-----------|--------|----------|
| Agent Registry | ✅ Working | `dispatcher/registry.py` — resolves agents, validates against gateway config |
| Workflow Engine | ✅ Working | `dispatcher/engine.py` — state machine v1.0, 6 phases, 9 transitions |
| State Manager | ✅ Working | `dispatcher/state_manager.py` — phase tracking, artifact verification, stall detection |
| Session Dispatch Layer (stub) | ❌ MOCK/STUB | `dispatcher/session_dispatch/engine.py` |
| Protocol Documentation | ✅ Complete | `dispatcher/PROTOCOL.md`, `dispatcher/SKILL.md` |
| State Schema | ✅ Documented | `dispatcher/STATE_SCHEMA.md` |

### 2.2 The Defect: spawn_agent() Returns Mock Success

File: `/home/deepsim/ds_eo_openclaw/dispatcher/session_dispatch/engine.py`

The critical path is in `SessionDispatcher.spawn_via_sessions_spawn_tool()`:
```python
def spawn_via_sessions_spawn_tool(self, target_agent_id, prompt_text, task_id=None, **kwargs):
    """Spawn using the actual OpenClaw sessions_spawn tool interface."""
    # TODO: invoke sessions_spawn tool from within an agent's runtime
    # result = await sessions_spawn(...)
    return SpawnResult(success=True, ...)  # ← Returns mock success
```

The method returns `SpawnResult(success=True)` without actually invoking OpenClaw's `sessions_spawn` tool. The `check_completion()` method similarly returns mock status.

### 2.3 Why This Matters

- **All automatic model tasks are blocked** — no agent can be dispatched to a target agent
- The manual mode works (human orchestrates handoffs), but the automatic model is non-functional at its core dispatch mechanism
- This is not a test gap — it's a fundamental infrastructure defect in the DS-EO framework itself
- TASK_DAL_002 and any future task requiring G1→G2 auto-dispatch are blocked by this

## 3. Root Cause Analysis

The Dispatcher was designed as a Python library that:
1. **Manages state** (phase tracking, transitions, artifacts) — ✅ working
2. **Orchestrates agent handoffs** via OpenClaw's `sessions_spawn` tool — ❌ unimplemented

The gap is between the Python dispatcher code and the actual OpenClaw runtime. When called from an agent's tool context, the dispatcher has no way to invoke `sessions_spawn` because:
- It runs as a Python library import, not as an agent tool
- It has no access to OpenClaw's tool execution system
- The spawn method is intentionally stubbed with TODO comments

## 4. Solution Design

### Option A: Bridge via OpenClaw Tool Wrapper (Recommended)

Transform `spawn_agent()` into a callable that wraps the actual `sessions_spawn` call through a proper interface:

```python
class SessionDispatcher:
    def spawn_agent(self, target_agent_id, prompt_text, task_id=None, ...):
        """Spawn an agent session via OpenClaw's sessions_spawn mechanism."""
        # This must work when called from:
        # 1. Within an agent tool context → call real sessions_spawn
        # 2. Externally (CLI, Python) → use gateway API or direct session creation
```

Implementation approach:
1. Create a `sessions_spawn_bridge.py` module that handles the dispatch mechanism
2. In agent context: wrap `sessions_spawn` as a tool call with proper parameters
3. In external context: use OpenClaw's internal session creation API
4. Add reliability checking: verify the returned session key actually corresponds to a running session

### Option B: Gateway API Integration

Use the gateway's HTTP API (or internal methods) for external dispatch, and agent tools for in-context dispatch:
- External: `POST /api/sessions` with agent config
- Agent context: tool call to `sessions_spawn` with proper marshaling

### Option C: Hybrid Pattern (Recommended — Combines A + reliability check)

1. **Dispatcher calls sessions_spawn** → returns `SpawnResult` with real session key
2. **Dispatcher runs a reliability check** → queries OpenClaw's session store to verify the session exists and is active
3. **If verification fails** → return `SpawnResult(success=False, error="Session creation verified failed")`
4. **If verification succeeds** → update state, log transition, continue

### 5. Reliability Checking (Non-Negotiable)

The fix must include a session verification step that **distinguishes real sessions from mock responses**:

```python
def verify_session_alive(self, session_key):
    """Verify an OpenClaw session actually exists and is running."""
    # Check against gateway's session store
    return {"exists": True, "status": "running", "agent_id": "..."}
```

This verification must be:
- Automatic on every spawn (no manual step)
- Part of the transition pipeline (before marking G2 as dispatched)
- Logged in the dispatcher state file for audit trail

## 6. Implementation Plan

### Step 1: Bridge Module (`dispatcher/session_dispatch/bridge.py`)
- Implement `spawn_real_session()` that correctly invokes OpenClaw session creation
- Handle both agent-tool context and external CLI context
- Return real `SpawnResult` with verified session key

### Step 2: Session Verification (`dispatcher/session_dispatch/verify.py`)
- Implement `verify_session_alive(session_key)` 
- Query OpenClaw's session store (via gateway API or internal methods)
- Return structured result indicating real vs mock

### Step 3: Update Dispatcher State Machine
- Modify `spawn_agent()` to call bridge + verification
- Update `check_completion()` to use real session status (not mock)
- Add reliability assertion in transition pipeline

### Step 4: Add Verification Tests
- Test that `spawn_agent()` creates a real OpenClaw session
- Test that `verify_session_alive()` correctly identifies active sessions
- Test the full G1→G2 dispatch cycle end-to-end

## 7. Deliverables

| Deliverable | File Path | Description |
|-------------|-----------|-------------|
| Bridge module | `dispatcher/session_dispatch/bridge.py` | Real session creation mechanism |
| Verification module | `dispatcher/session_dispatch/verify.py` | Session existence/status checker |
| Updated dispatcher engine | `dispatcher/session_dispatch/engine.py` | Integrated bridge + verification |
| Tests | `tests/test_dispatcher_session_bridge.py` | E2E dispatch verification |
| Task directory artifacts | `docs/development/reports/TASK_DS_EO_026/*` | Full DS-EO artifact set |

## 8. Gate Status

| Gate | Status | Notes |
|------|--------|-------|
| G0 (Task Creation) | ⬜ Pending | Awaiting CTO approval |
| G1 (User Approval of Plan) | ⬜ Pending | Awaiting user approval |
| G2 (Implementation Complete) | ⬜ Pending | — |
| G3 (Review Passes) | ⬜ Pending | — |
| G4 (Final Approval) | ⬜ Pending | — |

---

**CTO Plan produced by**: CTO (qwen3.6:35b)  
**Date**: 2026-08-05  
**Project**: DS-EO OpenClaw Edition  
**Repository**: ds-eo-openclaw / Deepsim-AI/DS-EO
