"""Phase 7 Tests: DSH Adapter P2+ Methods (Configurable Implementations).

Validates all newly implemented methods using mocked dsh_http_client.
"""

import sys
import os
from unittest.mock import patch, MagicMock
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ds_eo_dsh"))

from ds_eo_dsh.adapter.dsh_adapter import DshRuntimeAdapter


class TestArchiveSession:
    """archive_session (P2) tests."""

    def test_archive_dsh_path_success(self):
        adapter = DshRuntimeAdapter(base_url="https://dsh.example.com/api")
        
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.post.return_value = {"output_path": "/export/session_123.tar.gz"}
        adapter._client = mock_client
        
        result = adapter.archive_session("session-123", agent_id="agent-1")
        
        assert result.success is True
        assert result.details["output_path"] == "/export/session_123.tar.gz"
        mock_client.post.assert_called_once()

    def test_archive_unavailable(self):
        adapter = DshRuntimeAdapter()  # no base_url
        
        result = adapter.archive_session("session-123")
        
        assert result.success is False
        assert "unavailable" in result.error.lower()


class TestSpawnSession:
    """spawn_session (P2) tests."""

    def test_spawn_valid_config(self):
        adapter = DshRuntimeAdapter(base_url="https://dsh.example.com/api")
        
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.post.return_value = {"session_key": "new-session-key", "run_id": "run-42"}
        adapter._client = mock_client
        
        result = adapter.spawn_session({"model": "qwen3.6:35b", "agent_id": "a1"})
        
        assert result.success is True
        assert "session_key" in result.details

    def test_spawn_missing_model(self):
        adapter = DshRuntimeAdapter(base_url="https://dsh.example.com/api")
        
        result = adapter.spawn_session({})  # missing model key
        
        assert result.success is False
        assert "Missing required spawn config keys" in result.error


class TestSubmitTask:
    """submit_task (P2) tests."""

    def test_submit_success(self):
        adapter = DshRuntimeAdapter(base_url="https://dsh.example.com/api")
        
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.post.return_value = {"task_id": "task-99"}
        adapter._client = mock_client
        
        result = adapter.submit_task({"title": "test"}, role="cto")
        
        assert result.success is True
        assert result.details["task_id"] == "task-99"


class TestRunTools:
    """run_tools (P3) tests — including full policy gate."""

    def test_tool_allowed_by_policy(self):
        adapter = DshRuntimeAdapter(base_url="https://dsh.example.com/api")
        
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.post.return_value = {"output": "result"}
        adapter._client = mock_client
        
        # Allow list includes the tool
        policy = {"allow": ["exec", "read"]}
        result = adapter.run_tools("session-1", "exec", {"cmd": "ls"}, policy=policy)
        
        assert result.success is True

    def test_tool_denied_by_allow_policy(self):
        adapter = DshRuntimeAdapter()
        
        policy = {"allow": ["read"]}
        result = adapter.run_tools("session-1", "exec", {}, policy=policy)
        
        assert result.success is False
        assert "allow" in result.error.lower()

    def test_tool_denied_by_deny_policy(self):
        adapter = DshRuntimeAdapter()
        
        policy = {"deny": ["dangerous"]}
        result = adapter.run_tools("session-1", "dangerous", {}, policy=policy)
        
        assert result.success is False
        assert "denied" in result.error.lower()

    def test_tool_not_denied_by_other_deny_list(self):
        adapter = DshRuntimeAdapter()
        
        # No allow list, tool not in deny list → should still fail (no base_url)
        policy = {"deny": ["other"]}
        result = adapter.run_tools("session-1", "exec", {}, policy=policy)
        
        assert result.success is False  # fails because no DSH API


class TestAvailableModels:
    """available_models (P3) tests."""

    def test_available_models_from_dsh(self):
        adapter = DshRuntimeAdapter(base_url="https://dsh.example.com/api")
        
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.get.return_value = [
            {"id": "qwen3.6:35b", "context_window": 128000, "max_tokens": 4096},
            {"id": "qwen3.8:27b", "context_window": 128000, "max_tokens": 4096},
        ]
        adapter._client = mock_client
        
        result = adapter.available_models()
        
        assert len(result) == 2
        assert result[0].id == "qwen3.6:35b"
        assert result[0].provider == "dsh"

    def test_available_models_unavailable(self):
        adapter = DshRuntimeAdapter()
        
        result = adapter.available_models()
        
        assert result == []


class TestRunTask:
    """run_task (P4) tests."""

    def test_run_task_success(self):
        adapter = DshRuntimeAdapter(base_url="https://dsh.example.com/api")
        
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.post.return_value = {"success": True, "output": "done"}
        adapter._client = mock_client
        
        result = adapter.run_task("my-hook", {"arg": 1})
        
        assert result.success is True

    def test_run_task_unavailable(self):
        adapter = DshRuntimeAdapter()
        
        result = adapter.run_task("my-hook", {})
        
        assert result.success is False


class TestRegisterBinding:
    """register_binding (P4 — unchanged) tests."""

    def test_register_returns_true(self):
        adapter = DshRuntimeAdapter()
        
        assert adapter.register_binding("/test", lambda: None) is True


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
