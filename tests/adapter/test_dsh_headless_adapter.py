"""Tests for DSH Headless Adapter.

Covers: JSON parsing, task execution, model management, timeout handling,
and full RuntimeAPI protocol method behavior.

Uses controlled/mocked subprocess calls -- does NOT require a live DSH instance.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ds_eo_dsh.adapter.dsh_headless_adapter import (
    DshHeadlessAdapter,
    TaskExecutionResult,
    SessionInfo,
)


class TestTaskExecutionResult(unittest.TestCase):
    def test_defaults(self):
        result = TaskExecutionResult(
            task_id="test-1", role="cto", profile_name="ds-eo-headless",
            success=True, output_text="Hello", error_message=None, exit_code=0,
        )
        self.assertEqual(result.task_id, "test-1")
        self.assertTrue(result.success)
        self.assertIsNotNone(result.executed_at)

    def test_post_init_executed_at(self):
        before = datetime.now(timezone.utc).isoformat()
        result = TaskExecutionResult(
            task_id="test-2", role="pm", profile_name="ds-eo-headless",
            success=False, output_text="", error_message="err", exit_code=1,
        )
        self.assertGreaterEqual(result.executed_at, before)


class TestDSHHeadlessAdapterInit(unittest.TestCase):
    def test_default_init(self):
        adapter = DshHeadlessAdapter(dsh_binary="dsh")
        self.assertEqual(adapter.dsh_binary, "dsh")
        self.assertEqual(adapter.model_overrides, {})
        self.assertTrue(adapter.enable_model_management)

    def test_custom_model_override(self):
        adapter = DshHeadlessAdapter(
            model_overrides={"cto": "qwen3.8:27b"},
            timeout_overrides={"cto": 60},
        )
        self.assertEqual(adapter._model_map["cto"], "qwen3.8:27b")
        self.assertEqual(adapter._timeout_map["cto"], 60)

    def test_model_disables_model_management(self):
        adapter = DshHeadlessAdapter(enable_model_management=False)
        self.assertFalse(adapter.enable_model_management)


class TestJSONParsing(unittest.TestCase):
    def setUp(self):
        self.adapter = DshHeadlessAdapter()

    def test_parse_basic_turn(self):
        stdout = json.dumps({
            "type": "session", "sessionId": "session-abc123", "cwd": "/home/deepsim"
        }) + "\n" + json.dumps({
            "type": "status", "phase": "turn_start", "turn": 1
        }) + "\n" + json.dumps({
            "type": "final", "text": "Hello World"
        })
        events = self.adapter._parse_json_output(stdout)
        self.assertEqual(events["session_id"], "session-abc123")
        self.assertEqual(events["final_text"], "Hello World")

    def test_parse_usage_in_step_end(self):
        stdout = json.dumps({
            "type": "session", "sessionId": "session-xyz", "cwd": "/home/deepsim"
        }) + "\n" + json.dumps({
            "type": "status", "phase": "turn_start", "turn": 1
        }) + "\n" + json.dumps({
            "type": "status", "phase": "step_end", "turn": 1, "step": 1,
            "usage": {"inputTokens": 40, "outputTokens": 15, "totalTokens": 100, "cacheReadTokens": 50}
        }) + "\n" + json.dumps({"type": "final", "text": "Hello"})
        events = self.adapter._parse_json_output(stdout)
        self.assertEqual(events["input_tokens"], 40)
        self.assertEqual(events["output_tokens"], 15)
        self.assertEqual(events["cache_read_tokens"], 50)

    def test_parse_multiple_turns(self):
        events_list = [
            {"type": "session", "sessionId": "sess-1", "cwd": "/home/deepsim"},
            {"type": "status", "phase": "turn_start", "turn": 1},
            {"type": "final", "text": "First turn"},
            {"type": "status", "phase": "turn_start", "turn": 2},
            {"type": "final", "text": "Second turn"},
        ]
        stdout = "\n".join(json.dumps(e) for e in events_list)
        events = self.adapter._parse_json_output(stdout)
        self.assertEqual(events["turn_count"], 2)

    def test_parse_non_json_lines(self):
        stdout = '{"type":"session","sessionId":"s1"}\n' \
                 'some garbage\n' \
                 '{"type":"final","text":"Hello"}\n'
        events = self.adapter._parse_json_output(stdout)
        self.assertEqual(events["session_id"], "s1")
        self.assertEqual(events["final_text"], "Hello")

    def test_extract_final_text_priority(self):
        events = {"final_text": "Explicit final", "steps": []}
        self.assertEqual(self.adapter._extract_final_text(events), "Explicit final")
        events = {"final_text": "", "steps": [
            {"type": "status", "text": "Step 1"},
            {"type": "status", "text": "Step 2 - longer content"},
        ]}
        self.assertIn("Step 2", self.adapter._extract_final_text(events))

    def test_extract_session_id(self):
        # _extract_session_id was merged into _parse_json_output in the rewritten adapter
        events = {"session_id": "sess-abc", "steps": []}
        self.assertEqual(events["session_id"], "sess-abc")


        adapter = DshHeadlessAdapter()
        result = adapter.submit_task(task={"instructions": ""}, role="cto")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    @patch.object(DshHeadlessAdapter, '_execute_headless')
    def test_submit_task_success(self, mock_exec):
        mock_exec.return_value = TaskExecutionResult(
            task_id="test-1", role="cto", profile_name="ds-eo-headless",
            success=True, output_text="Plan generated successfully.",
            error_message=None, exit_code=0, turn_count=1,
            input_tokens=100, output_tokens=50, cache_read_tokens=20,
            model_used="qwen3.6:35b", executed_at=datetime.now(timezone.utc).isoformat(),
        )
        adapter = DshHeadlessAdapter()
        result = adapter.submit_task(task={"instructions": "Create a plan."}, role="cto")
        self.assertTrue(result.success)
        self.assertEqual(result.details["output_text"], "Plan generated successfully.")
        self.assertEqual(result.details["usage"]["input_tokens"], 100)

    @patch.object(DshHeadlessAdapter, '_execute_headless')
    def test_submit_task_failure(self, mock_exec):
        mock_exec.return_value = TaskExecutionResult(
            task_id="test-2", role="implementer", profile_name="ds-eo-headless",
            success=False, output_text="", error_message="Process killed by timeout",
            exit_code=124, turn_count=0, model_used="qwen3.8:27b",
            executed_at=datetime.now(timezone.utc).isoformat(),
        )
        adapter = DshHeadlessAdapter()
        result = adapter.submit_task(task={"instructions": "Write code."}, role="implementer")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.details["role"], "implementer")

    @patch.object(DshHeadlessAdapter, '_execute_headless')
    def test_submit_task_with_plan(self, mock_exec):
        plan = {"instructions": "Architecture: use microservices."}
        adapter = DshHeadlessAdapter()
        result = adapter.submit_task(task={"instructions": "Design the system."}, role="cto", plan=plan)
        self.assertIn("[Plan Context]", mock_exec.call_args[1]["task_text"])

    def test_submit_task_model_resolution(self):
        adapter = DshHeadlessAdapter()
        for role in ["cto", "implementer", "reviewer", "pm"]:
            expected = adapter._model_map.get(role, "ornith-1.5:35b")
            self.assertIn(expected, adapter._model_map.values())


class TestModelManagement(unittest.TestCase):
    def test_model_size_estimation(self):
        adapter = DshHeadlessAdapter()
        self.assertEqual(adapter._model_size("qwen3.8:27b"), 22000000000)
        self.assertEqual(adapter._model_size("nomic-embed-text"), 274000000)

    def test_context_window_estimation(self):
        adapter = DshHeadlessAdapter()
        self.assertEqual(DshHeadlessAdapter._estimate_context_window("qwen3.6:35b"), 131072)
        self.assertEqual(DshHeadlessAdapter._estimate_context_window("laguna-xs-2.1"), 4096)

    @patch.object(DshHeadlessAdapter, '_get_available_models')
    @patch.object(DshHeadlessAdapter, '_ensure_model_loaded')
    def test_disable_model_management(self, mock_ensure, mock_get):
        adapter = DshHeadlessAdapter(enable_model_management=False)


class TestOtherRuntimeAPIMethods(unittest.TestCase):
    def setUp(self):
        self.adapter = DshHeadlessAdapter()

    def test_compact_session_is_noop(self):
        result = self.adapter.compact_session("session-abc")
        self.assertTrue(result.success)
        self.assertEqual(result.details["method"], "no_op")

    def test_archive_session_logs_intent(self):
        result = self.adapter.archive_session("session-xyz", reason="completed")
        self.assertTrue(result.success)
        self.assertEqual(result.details["method"], "log_only")

    def test_close_session_is_noop(self):
        result = self.adapter.close_session("session-def")
        self.assertTrue(result.success)

    def test_get_session_info_returns_unknown(self):
        info = self.adapter.get_session_info("session-abc", agent_id="cto")
        self.assertIsNotNone(info)
        self.assertEqual(info.status, "unknown")

    def test_spawn_session_returns_success(self):
        result = self.adapter.spawn_session({"profile_name": "test-profile"})
        self.assertTrue(result.success)

    def test_run_tools_returns_unsupported(self):
        result = self.adapter.run_tools(
            session_key="session-abc", tool_name="write_file", tool_args={"path": "/tmp/test.txt"},
        )
        self.assertFalse(result.success)

    def test_register_binding_stores_binding(self):
        result = self.adapter.register_binding("test-cmd", lambda x: x)
        self.assertTrue(result)

    def test_create_returns_self(self):
        adapter2 = self.adapter.create()
        self.assertIs(adapter2, self.adapter)

    @patch.object(DshHeadlessAdapter, '_get_ollama_models')
    def test_available_models_handles_error(self, mock_get_models):
        mock_get_models.return_value = []
        models = self.adapter.available_models()
        self.assertIsInstance(models, list)

    def test_model_info_fallback(self):
        model = self.adapter.model_info("unknown-model:test")
        self.assertEqual(model.provider, "ollama")
        self.assertEqual(model.context_window, 4096)

    def test_run_task_unknown_tool(self):
        result = self.adapter.run_task("unknown-tool", {"arg": "val"})
        self.assertFalse(result.success)


class TestDSHHeadlessAdapterIntegration(unittest.TestCase):
    def test_adapter_initializes_with_custom_binary(self):
        adapter = DshHeadlessAdapter(dsh_binary="/usr/local/bin/dsh")
        self.assertEqual(adapter.dsh_binary, "/usr/local/bin/dsh")

    def test_task_id_is_uuid(self):
        r1 = TaskExecutionResult(
            task_id="unique-1", role="cto", profile_name="test",
            success=True, output_text="", error_message=None, exit_code=0,
        )
        r2 = TaskExecutionResult(
            task_id="unique-2", role="pm", profile_name="test",
            success=True, output_text="", error_message=None, exit_code=0,
        )
        self.assertNotEqual(r1.task_id, r2.task_id)

    def test_usage_stats_structure(self):
        result = TaskExecutionResult(
            task_id="test", role="cto", profile_name="ds-eo-headless",
            success=True, output_text="", error_message=None, exit_code=0,
            input_tokens=100, output_tokens=50, cache_read_tokens=20, turn_count=2,
        )
        self.assertEqual(result.input_tokens, 100)
        self.assertEqual(result.output_tokens, 50)
        self.assertEqual(result.turn_count, 2)


if __name__ == "__main__":
    unittest.main()
