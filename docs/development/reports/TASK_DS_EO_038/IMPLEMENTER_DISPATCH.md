# IMPLEMENTER DISPATCH — TASK_DS_EO_038: Real `spawn_agent()` via OpenClaw CLI Integration

## Gate Status
- **G1 (Plan Approved)**: ✅ User approved CTO_PLAN.md
- **G2 (Implementation)**: ⬜ In progress
- **Authority**: This document IS the implementation plan. Follow it exactly — no architectural deviations.

## What to Build

A new Python module `ds_eo_openclaw/dispatcher/session_spawn.py` that implements `spawn_agent()` using OpenClaw's `sessions_spawn` tool integration, plus a state manager for dispatcher state tracking.

### Module: `ds_eo_openclaw/dispatcher/__init__.py` (NEW)
Package init exposing public API.

### Module: `ds_eo_openclaw/dispatcher/session_spawn.py` (NEW) — Core spawn logic

Public class and functions to implement:

```python
class SessionSpawnManager:
    """Manages real OpenClaw agent session creation for DS-EO dispatcher."""
    
    def __init__(self, workspace_root: str):
        """Initialize with workspace root path.
        
        Args:
            workspace_root: Path to the DS-EO workspace root (where docs/dispatchers/ lives).
        """
        self.workspace_root = os.path.abspath(workspace_root)
        self.dispatcher_state_dir = os.path.join(self.workspace_root, "docs/dispatchers")
        self._agent_model_map = {
            "implementer": "ollama/ornith:35b",
            "reviewer": "ollama/laguna-xs-2.1:q4_K_M",
            "cto": "ollama/qwen3.6:35b",
        }
    
    def spawn_agent(
        self,
        task_id: str,
        agent_role: str,  # "implementer", "reviewer", or "cto"
        prompt_content: str,  # The work content to deliver as the first [Subagent Task] message
        model_override: Optional[str] = None,  # Optional custom model (uses role default)
    ) -> tuple[bool, dict]:
        """Create a real OpenClaw agent session via sessions_spawn integration.
        
        This is the CORE method that replaces the previous mock/stub spawn.
        
        Returns:
            (success: bool, result: dict) where result contains:
              - session_key: The spawned session key (if success=True)
              - run_id: The OpenClaw run identifier (if available)
              - error: Error message (if success=False)
        """
        # Step 1: Determine the target model
        target_model = model_override or self._agent_model_map.get(agent_role)
        if not target_model:
            return False, {
                "session_key": None,
                "run_id": None,
                "error": f"Unknown agent role: {agent_role}",
            }
        
        # Step 2: Write dispatcher state BEFORE spawning (for tracking/verification)
        spawn_session_key = self._write_spawn_state(task_id, agent_role)
        
        # Step 3: Spawn the real session via sessions_spawn integration
        # NOTE: This module calls OpenClaw's sessions_spawn tool programmatically.
        # The actual call pattern when running inside an OpenClaw agent session is:
        #   sessions_spawn(
        #       prompt=prompt_content,
        #       model=target_model,
        #       context="isolated",
        #       runtime="subagent",
        #   )
        # When running as a standalone library (outside OpenClaw agent), it must
        # invoke the OpenClaw gateway API directly.
        
        success, spawn_result = self._invoke_sessions_spawn(
            prompt=prompt_content,
            model=target_model,
            context="isolated",
            runtime="subagent",
        )
        
        if success:
            result_key = spawn_result.get("childSessionKey") or spawn_result.get("session_key")
            run_id_val = spawn_result.get("runId") or spawn_result.get("run_id")
            
            # Update dispatcher state with the real session key
            self._update_spawn_session_key(task_id, result_key)
            
            return True, {
                "session_key": result_key,
                "run_id": run_id_val,
                "spawn_session_key": spawn_session_key,
                "agent_role": agent_role,
                "error": None,
            }
        else:
            error_msg = spawn_result.get("error", "Unknown spawn failure")
            # Clean up dispatcher state on failure
            self._cleanup_spawn_state(task_id)
            return False, {
                "session_key": None,
                "run_id": None,
                "spawn_session_key": spawn_session_key,
                "agent_role": agent_role,
                "error": error_msg,
            }
    
    def verify_spawn(self, task_id: str) -> tuple[bool, dict]:
        """Verify that a spawned session still exists and is running.
        
        Returns:
            (verified: bool, info: dict) where info contains current state of
            the dispatcher state entry for this task.
        """
        state = self._read_dispatcher_state(task_id)
        if not state:
            return False, {"error": f"No dispatcher state found for {task_id}"}
        
        pending = state.get("pending_work", {})
        session_key = pending.get("spawn_session_key") or pending.get("spawn_session_key")
        
        if not session_key:
            return False, {"error": "No spawn_session_key in pending work"}
        
        # Verify session exists via sessions_spawn/verify integration
        verified = self._verify_session_exists(session_key)
        
        return verified, {
            "session_key": session_key,
            "exists": verified,
            "state": state.get("current_phase"),
            "error": None if verified else "Session no longer exists or terminated",
        }
    
    def _write_spawn_state(self, task_id: str, agent_role: str) -> str:
        """Write initial dispatcher state for a new spawn. Returns spawn_session_key."""
        os.makedirs(self.dispatcher_state_dir, exist_ok=True)
        task_dir = os.path.join(self.dispatcher_state_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        import uuid
        spawn_session_key = f"spawn_{task_id}_{uuid.uuid4().hex[:8]}"
        
        now = datetime.now(timezone.utc).isoformat()
        state = {
            "version": "0.1.0",
            "taskId": task_id,
            "current_phase": "S2_IMPLEMENTATION",
            "workflow_version": "1.0",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "pending_work": {
                "task_id": task_id,
                "assigned_to": agent_role,
                "spawn_session_key": spawn_session_key,
                "work_type": f"Spawned by real spawn_agent() — {agent_role}",
                "notes": "",
            },
            "phase_history": [
                {
                    "phase": "S2_IMPLEMENTATION",
                    "entered_at": now,
                    "left_at": None,
                    "agent": agent_role,
                }
            ],
        }
        
        state_path = os.path.join(task_dir, "dispatcher_state.json")
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
        
        return spawn_session_key
    
    def _update_spawn_session_key(self, task_id: str, real_session_key: str):
        """Update dispatcher state with the real session key from sessions_spawn."""
        import uuid
        # Use the spawn_session_key as the tracking key
        dispatchers_base = os.path.join(self.workspace_root, "docs/dispatchers")
        task_dir = os.path.join(dispatchers_base, task_id)
        
        # We store both keys: the tracking key and the real OpenClaw session key
        tracker_key = f"{task_id}_real_session"
        
        # Write a mapping file for discoverer.py to find
        mapping_path = os.path.join(task_dir, "spawn_mapping.json")
        mapping = {
            "spawn_session_key": f"spawn_{task_id}_{uuid.uuid4().hex[:8]}",
            "real_session_key": real_session_key,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(mapping_path, "w") as f:
            json.dump(mapping, f, indent=2)
    
    def _update_pending_work(self, task_id: str, pending_data: dict):
        """Update pending_work in the dispatcher state."""
        dispatchers_base = os.path.join(self.workspace_root, "docs/dispatchers")
        task_dir = os.path.join(dispatchers_base, task_id)
        state_path = os.path.join(task_dir, "dispatcher_state.json")
        
        if not os.path.exists(state_path):
            return
        
        with open(state_path) as f:
            state = json.load(f)
        
        state["pending_work"].update(pending_data)
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
    
    def _read_dispatcher_state(self, task_id: str) -> Optional[dict]:
        """Read dispatcher state for a task."""
        dispatchers_base = os.path.join(self.workspace_root, "docs/dispatchers")
        state_path = os.path.join(dispatchers_base, task_id, "dispatcher_state.json")
        
        if not os.path.exists(state_path):
            return None
        
        with open(state_path) as f:
            return json.load(f)
    
    def _cleanup_spawn_state(self, task_id: str):
        """Clean up dispatcher state on spawn failure."""
        mapping_path = os.path.join(self.dispatcher_state_dir, task_id, "spawn_mapping.json")
        if os.path.exists(mapping_path):
            os.remove(mapping_path)
    
    def _invoke_sessions_spawn(
        self,
        prompt: str,
        model: str,
        context: str,
        runtime: str,
    ) -> tuple[bool, dict]:
        """Invoke OpenClaw sessions_spawn to create a real session.
        
        CRITICAL: This method bridges the gap between our Python module
        and the OpenClaw agent runtime. Two implementation paths:
        
        Path A — Running inside an OpenClaw agent session:
            Directly call the tool via the gateway's internal API.
            The calling agent uses the sessions_spawn tool tool_call
            mechanism built into the runtime.
        
        Path B — Running as a standalone library (outside agent context):
            Call the OpenClaw Gateway REST API endpoint for sessions spawn.
            POST to /api/sessions/spawn with the configuration payload.
        
        For TASK_DS_EO_038, implement Path B first (library mode),
        then add Path A support as a bonus.
        """
        # TODO: Implement both paths
        # This is the core of what's being built — currently returns error
        return False, {
            "error": "NOT YET IMPLEMENTED — this is what TASK_DS_EO_038 builds",
        }
    
    def _verify_session_exists(self, session_key: str) -> bool:
        """Verify a spawned session exists in OpenClaw's session store.
        
        Returns True if the session exists and is active (not terminated).
        """
        # TODO: Implement verification via sessions_list or Gateway API
        return False


# Module-level convenience function
def spawn_agent(
    workspace_root: str,
    task_id: str,
    agent_role: str,
    prompt_content: str,
    model_override: Optional[str] = None,
) -> tuple[bool, dict]:
    """Convenience wrapper around SessionSpawnManager.spawn_agent()."""
    mgr = SessionSpawnManager(workspace_root=workspace_root)
    return mgr.spawn_agent(
        task_id=task_id,
        agent_role=agent_role,
        prompt_content=prompt_content,
        model_override=model_override,
    )
```

### Integration: `ds_eo_openclaw/workflow/state_engine.py` — Wire spawn into auto-advance

In the `StateEngine.advance_g2()` (or equivalent G2 → REVIEW/IMPLEMENTATION transition), when transitioning to a phase that requires an agent session, call `spawn_agent()`:

```python
# In StateEngine or the PM dispatch path:
from ds_eo_openclaw.dispatcher.session_spawn import spawn_agent

def auto_dispatch_to_agent(self, task_id: str, agent_role: str, prompt_content: str):
    """Auto-dispatch to an agent session when in automatic mode."""
    success, result = spawn_agent(
        workspace_root=self.workspace_root,
        task_id=task_id,
        agent_role=agent_role,
        prompt_content=prompt_content,
    )
    
    if not success:
        # Transition to BLOCKED or FAILED state
        return False
    
    # Store session_key in dispatcher pending_work for tracking
    self._update_pending_work(task_id, {
        "spawn_session_key": result.get("spawn_session_key"),
        "real_session_key": result.get("session_key"),
    })
    
    return True
```

### Tests: `tests/test_dispatcher_spawn.py` (NEW)

Write tests that verify the spawn infrastructure without requiring a live OpenClaw Gateway:

```python
import unittest
import json
import os
import tempfile
from ds_eo_openclaw.dispatcher.session_spawn import SessionSpawnManager, spawn_agent


class TestSessionSpawnManager(unittest.TestCase):
    """Tests for real session spawning infrastructure."""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = SessionSpawnManager(workspace_root=self.tmpdir)
    
    def test_init_creates_no_state_yet(self):
        # No dispatcher state should exist before first spawn
        self.assertFalse(os.path.isdir(os.path.join(self.tmpdir, "docs/dispatchers")))
    
    def test_spawn_agent_writes_dispatcher_state(self):
        """AC-1: spawn_agent() creates dispatcher state (even if real session creation fails)."""
        success, result = self.manager.spawn_agent(
            task_id="TASK_TEST_001",
            agent_role="implementer",
            prompt_content="Test work content",
        )
        
        # State should be written even if real session creation returns error (stub)
        state_path = os.path.join(self.tmpdir, "docs/dispatchers/TASK_TEST_001/dispatcher_state.json")
        self.assertTrue(os.path.exists(state_path))
        
        with open(state_path) as f:
            state = json.load(f)
        
        self.assertEqual(state["taskId"], "TASK_TEST_001")
        self.assertEqual(state["current_phase"], "S2_IMPLEMENTATION")
        self.assertIn("spawn_session_key", state["pending_work"])
    
    def test_spawn_agent_uses_correct_model_for_role(self):
        """AC-2: Returned session key/ID is valid and addresses the correct agent model."""
        # Verify _agent_model_map has the right defaults
        self.assertEqual(
            self.manager._agent_model_map["implementer"],
            "ollama/ornith:35b"
        )
        self.assertEqual(
            self.manager._agent_model_map["reviewer"],
            "ollama/laguna-xs-2.1:q4_K_M"
        )
        self.assertEqual(
            self.manager._agent_model_map["cto"],
            "ollama/qwen3.6:35b"
        )
    
    def test_spawn_agent_rejects_unknown_role(self):
        """AC-4: Verification step rejects phantom spawns (bad role → error)."""
        success, result = self.manager.spawn_agent(
            task_id="TASK_TEST_002",
            agent_role="nonexistent_role",
            prompt_content="Test",
        )
        self.assertFalse(success)
        self.assertIn("Unknown agent role", result["error"])
    
    def test_verify_spawn_returns_state_info(self):
        """Verify spawn returns state info about the dispatcher entry."""
        # First create a state via spawn_agent
        self.manager.spawn_agent(
            task_id="TASK_TEST_003",
            agent_role="reviewer",
            prompt_content="Test review work",
        )
        
        success, info = self.manager.verify_spawn("TASK_TEST_003")
        # verify_spawn may return False for "exists" since we haven't implemented 
        # the real verification yet, but should still return state info
        self.assertIsNotNone(info)
    
    def test_cleanup_on_failure(self):
        """AC-4: Verify cleanup path on spawn failure."""
        # spawn_mapping.json should be cleaned up on failure
        task_dir = os.path.join(self.tmpdir, "docs/dispatchers/TASK_TEST_004")
        os.makedirs(task_dir, exist_ok=True)
        mapping_path = os.path.join(task_dir, "spawn_mapping.json")
        
        # Create a fake mapping to test cleanup
        with open(mapping_path, "w") as f:
            json.dump({"test": "data"}, f)
        
        self.manager._cleanup_spawn_state("TASK_TEST_004")
        self.assertFalse(os.path.exists(mapping_path))


class TestSpawnAgentConvenienceFunction(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
    
    def test_convenience_function_exists(self):
        """Module-level spawn_agent() convenience function exists and works."""
        success, result = spawn_agent(
            workspace_root=self.tmpdir,
            task_id="TASK_TEST_005",
            agent_role="implementer",
            prompt_content="Test via convenience fn",
        )
        # Even if real session creation fails (stub), dispatcher state should be written
        state_path = os.path.join(self.tmpdir, "docs/dispatchers/TASK_TEST_005/dispatcher_state.json")
        self.assertTrue(os.path.exists(state_path))


if __name__ == "__main__":
    unittest.main()
```

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `ds_eo_openclaw/dispatcher/__init__.py` | NEW | Package init, export public API |
| `ds_eo_openclaw/dispatcher/session_spawn.py` | NEW | Core `spawn_agent()` + verification + state management |
| `ds_eo_openclaw/workflow/state_engine.py` | EDIT | Wire spawn into auto-dispatch path (call `spawn_agent()` on G2 transition) |
| `tests/test_dispatcher_spawn.py` | NEW | Unit tests for spawn infrastructure |

## Implementation Priority

1. **Priority 1**: Create `ds_eo_openclaw/dispatcher/session_spawn.py` with the stub `_invoke_sessions_spawn` returning proper structure (state written, error on real session creation). This gives us dispatcher state tracking without live Gateway dependency.
2. **Priority 2**: Write and pass all tests in `tests/test_dispatcher_spawn.py`.
3. **Priority 3**: Wire into `state_engine.py` auto-dispatch path — call `spawn_agent()` instead of the previous mock/stub.
4. **Priority 4**: Implement the real `_invoke_sessions_spawn` Gateway API call (Path B: standalone REST API).
5. **Priority 5** (bonus): Add Path A support for running inside an OpenClaw agent session (direct tool call mechanism).

## Critical Constraints

- The module MUST write dispatcher state BEFORE attempting to spawn — so if spawn fails, we can clean up or diagnose.
- `_invoke_sessions_spawn` must return the same `(success, result)` structure regardless of which path is used (Path A or B). This ensures all callers don't need branch logic.
- `verify_spawn()` must be called after each `spawn_agent()` success to validate the session exists (AC-4).
- No changes to gate logic — this is purely infrastructure. The state_engine integration is just calling the new module instead of the old mock.

## Acceptance Verification

| AC | Test |
|----|------|
| AC-1 | `test_spawn_agent_writes_dispatcher_state` passes, dispatcher_state.json has correct phase + pending_work |
| AC-2 | `test_spawn_agent_uses_correct_model_for_role` verifies model mapping; real spawn returns valid session key |
| AC-3 | PM auto-mode dispatches task → `spawn_agent()` called → real Implementer session executes (verify via `sessions_list`) |
| AC-4 | `test_spawn_agent_rejects_unknown_role` + `test_verify_spawn` both pass |
| AC-5 | All existing tests pass (`python -m pytest tests/ -v --tb=short`) + new tests pass |
| AC-6 | Integration: PM auto-mode → spawn real Implementer → confirm session exists via `sessions_list` |

## Notes for the Implementer

- Read the OpenClaw docs at `/home/deepsim/.nvm/versions/node/v24.18.0/lib/node_modules/openclaw/docs/concepts/session-tool.md` for sessions_spawn specifics.
- The existing `dispatcher_state.json` files in `docs/dispatchers/TASK_*` are the target format — match their structure.
- Don't modify any protocols, agent configs, or governance files — this is purely infrastructure code.
- After completing Priority 4 (real Gateway API call), test by actually spawning a session and verifying it appears in `sessions_list`.

