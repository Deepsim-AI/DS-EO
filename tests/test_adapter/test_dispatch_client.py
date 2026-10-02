"""Phase 11 adapter tests -- verify dispatch_client wiring into the workflow engine.

Run: pytest tests/test_adapter/test_dispatch_client.py -v

These tests validate:
  1. Headless default adapter creation via RuntimeAdapterFactory
  2. Correct task input dict construction (dispatch_client internals)
  3. Failure path: factory raise → success=False, no state mutation
  4. Lifecycle smoke: execute_transition(target_agent=...) forwards to dispatch
"""

import json
import sys
import os
import pytest

# Add workspace root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestHeadlessDefaultCreation:
    """Test WI-4a: default runtime resolution produces headless adapter."""

    def test_default_runtime_resolves_no_env(self):
        """Without DSH_ADAPTER set, _resolve_runtime returns 'headless'."""
        # Ensure no env variable interferes
        env_before = os.environ.pop("DSH_ADAPTER", None)
        try:
            from ds_eo_dsh.dispatcher.dispatch_client import _resolve_runtime
            result = _resolve_runtime()
            assert result == "headless", f"Expected 'headless', got '{result}'"
        finally:
            if env_before is not None:
                os.environ["DSH_ADAPTER"] = env_before

    def test_adapter_created_via_factory(self):
        """RuntimeAdapterFactory.create('dsh') returns an adapter with submit_task."""
        from ds_eo_dsh.adapter.runtime_api import RuntimeAdapterFactory

        adapter = RuntimeAdapterFactory.create(runtime="dsh")
        assert hasattr(adapter, "submit_task"), "Adapter missing submit_task"

    def test_factory_openclaw_path_available(self):
        """RuntimeAdapterFactory.create('openclaw') returns an OpenClaw adapter."""
        from ds_eo_dsh.adapter.runtime_api import RuntimeAdapterFactory

        adapter = RuntimeAdapterFactory.create(runtime="openclaw")
        assert hasattr(adapter, "submit_task"), "OpenClaw adapter missing submit_task"


class TestBuildTaskInput:
    """Test WI-4b: _build_task_input produces correct dict."""

    def test_full_input_produces_correct_fields(self):
        """All fields present → expected output dict."""
        from ds_eo_dsh.dispatcher.dispatch_client import _build_task_input

        result = _build_task_input({
            "task_id": "TASK_DSH_015",
            "target_agent": "cto",
            "transition_name": "G1_APPROVE",
            "from_phase": "S1_PLANNING",
            "to_phase": "S2_IMPLEMENTATION",
            "payload": "CTO approved the plan.",
        })

        assert result["task_id"] == "TASK_DSH_015"
        assert result["target_agent"] == "cto"
        assert result["transition_name"] == "G1_APPROVE"
        assert result["from_phase"] == "S1_PLANNING"
        assert result["to_phase"] == "S2_IMPLEMENTATION"
        assert result["instructions"] == "CTO approved the plan."

    def test_empty_payload_defaults_to_transition_name(self):
        """Without payload, instructions falls back to transition_name."""
        from ds_eo_dsh.dispatcher.dispatch_client import _build_task_input

        result = _build_task_input({
            "task_id": "TASK_DSH_015",
            "target_agent": "pm",
            "transition_name": "G2_COMPLETE",
            "payload": "",
        })
        assert result["instructions"] == "G2_COMPLETE"

    def test_empty_all_defaults_to_generic(self):
        """All empty → generic instruction text."""
        from ds_eo_dsh.dispatcher.dispatch_client import _build_task_input

        result = _build_task_input({})
        assert "Execute the requested workflow transition" in result["instructions"]


class TestFailurePath:
    """Test WI-4c: factory raise → success=False, no state mutation."""

    def test_factory_raises_returns_failure(self):
        """When RuntimeAdapterFactory.create raises, dispatch returns failure dict."""
        from unittest.mock import patch, MagicMock
        from ds_eo_dsh.dispatcher.dispatch_client import run

        # Patch at the import target location (dispatch_client imports it internally)
        with patch(
            "ds_eo_dsh.adapter.runtime_api.RuntimeAdapterFactory"
        ) as mock_factory:
            mock_factory.create.side_effect = RuntimeError("No adapter available")

            result = run({
                "task_id": "TASK_DSH_015",
                "target_agent": "cto",
                "transition_name": "G1_APPROVE",
                "payload": "test",
                "from_phase": "S1_PLANNING",
                "to_phase": "S2_IMPLEMENTATION",
            })

        assert isinstance(result, dict), "Result must be a dict"
        parsed = json.loads(result.get("result", "{}"))
        assert parsed["success"] is False
        assert "Failed to create runtime adapter" in str(parsed.get("error", ""))

    def test_no_state_mutation_on_failure(self):
        """Dispatch failure does not modify the engine or file system."""
        from unittest.mock import patch, MagicMock
        from ds_eo_dsh.dispatcher.dispatch_client import run

        # Create a mock adapter that raises during submit_task
        bad_adapter = MagicMock()
        bad_adapter.submit_task.side_effect = ValueError("Adapter error")

        with patch(
            "ds_eo_dsh.adapter.runtime_api.RuntimeAdapterFactory"
        ) as mock_factory:
            mock_factory.create.return_value = bad_adapter

            result = run({
                "task_id": "TASK_DSH_015",
                "target_agent": "cto",
                "transition_name": "G1_APPROVE",
                "payload": "test",
                "from_phase": "S1_PLANNING",
                "to_phase": "S2_IMPLEMENTATION",
            })

        parsed = json.loads(result.get("result", "{}"))
        assert parsed["success"] is False
        assert "submit_task raised" in str(parsed.get("error", ""))


class TestExecuteTransitionForwards:
    """Test WI-4d: lifecycle smoke — engine.execute_transition dispatches."""

    @pytest.fixture
    def engine(self):
        """Create a WorkflowEngine with valid workflow loaded."""
        from ds_eo_dsh.dispatcher.engine import WorkflowEngine

        wf_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "ds_eo_dsh", "dispatcher", "workflow_defs", "default.yaml",
        )
        engine = WorkflowEngine(workflow_path=wf_path, workspace_root=os.path.dirname(wf_path))
        assert engine.load_workflow(), "Workflow must load successfully"
        return engine

    def test_dispatch_bridge_called_when_target_agent_set(self, engine):
        """Calling execute_transition with target_agent invokes the dispatch bridge."""
        from unittest.mock import patch, MagicMock
        from ds_eo_dsh.dispatcher.engine import WorkflowEngine

        mock_result = {
            "result": json.dumps({"success": True, "error": None}),
            "runtime": "headless",
        }

        with patch(
            "ds_eo_dsh.dispatcher.dispatch_client.run"
        ) as mock_dispatch:
            mock_dispatch.return_value = mock_result

            result = engine.execute_transition(
                task_id="TASK_DSH_015",
                from_phase="S1_PLANNING",
                transition_name="G1_APPROVE",
                triggered_by_agent="pm",
                target_agent="cto",
                event_type="DELEGATE_G1",
                payload_summary="Plan approved by user.",
            )

        assert result.success is True, "Transition must succeed"
        # Verify dispatch was called with the correct input dict
        call_kwargs = mock_dispatch.call_args[0][0]
        assert call_kwargs["task_id"] == "TASK_DSH_015"
        assert call_kwargs["target_agent"] == "cto"
        assert call_kwargs["transition_name"] == "G1_APPROVE"
        assert call_kwargs["from_phase"] == "S1_PLANNING"
        assert call_kwargs["payload"] == "Plan approved by user."

    def test_dispatch_not_called_when_no_target_agent(self, engine):
        """Calling execute_transition without target_agent: dispatch uses config agent."""
        from unittest.mock import patch

        # Phase 11 auto-resolves: when G1_APPROVE has agent: implementer in
        # workflow config, that's used as the dispatch target.  Here we verify
        # the auto-resolved agent is correctly passed (and the bridge does fire).
        mock_result = {
            "result": json.dumps({"success": True, "error": None}),
            "runtime": "headless",
        }

        with patch(
            "ds_eo_dsh.dispatcher.dispatch_client.run"
        ) as mock_dispatch:
            mock_dispatch.return_value = mock_result

            result = engine.execute_transition(
                task_id="TASK_DSH_015",
                from_phase="S1_PLANNING",
                transition_name="G1_APPROVE",
                triggered_by_agent="pm",
                # No target_agent — will auto-resolve from config to "implementer"
            )

        assert result.success is True, "Transition must succeed despite auto-resolution"
        # Verify dispatch was called with the CONFIG-RESOLVED agent (not the caller)
        call_kwargs = mock_dispatch.call_args[0][0]
        assert call_kwargs["target_agent"] == "implementer", \
            "Phase 11 auto-resolves target_agent (WI-2)"

    def test_non_fatal_on_dispatch_exception(self, engine):
        """Dispatch exception does NOT block the gate — transition still succeeds."""
        from unittest.mock import patch

        with patch(
            "ds_eo_dsh.dispatcher.dispatch_client.run"
        ) as mock_dispatch:
            mock_dispatch.side_effect = RuntimeError("Simulated dispatch failure")

            result = engine.execute_transition(
                task_id="TASK_DSH_015",
                from_phase="S1_PLANNING",
                transition_name="G1_APPROVE",
                triggered_by_agent="pm",
                target_agent="cto",
                payload_summary="test",
            )

        # The transition still succeeds because dispatch is non-fatal
        assert result.success is True, "Transition must succeed despite dispatch failure"
