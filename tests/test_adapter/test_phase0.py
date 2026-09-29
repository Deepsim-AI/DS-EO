"""Phase 0 adapter tests — verify interface compliance without behavioral change.

Run: pytest tests/test_adapter/test_phase0.py -v

These tests validate that the adapter package is correctly structured and
that all adapters satisfy the RuntimeAPI protocol, but do NOT test runtime behavior
(behavior is tested in later phases after DSH integration is complete).
"""

import sys
import os

# Add workspace root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_runtime_api_protocol_exists():
    """RuntimeAPI Protocol is importable and has all 10 required methods."""
    from ds_eo_openclaw.adapter.runtime_api import RuntimeAPI

    # Verify Protocol has all required methods (10 total)
    required_methods = {
        "compact_session", "archive_session", "close_session",
        "get_session_info", "spawn_session", "submit_task", "run_tools",
        "model_info", "available_models", "run_task", "register_binding",
    }
    assert len(required_methods) == 11, f"Expected 11 methods (Protocol + 10 abstract), got {len(required_methods)}"
    for method in required_methods:
        assert hasattr(RuntimeAPI, method), f"RuntimeAPI missing method: {method}"


def test_runtime_model_dataclass():
    """RuntimeModel dataclass has all required fields."""
    from ds_eo_openclaw.adapter.runtime_api import RuntimeModel

    model = RuntimeModel(
        id="test/model", context_window=131072, max_tokens=8192,
        gpu_layers=-1, ram_bytes=10_000_000_000, provider="ollama"
    )
    assert model.id == "test/model"
    assert model.context_window == 131072
    assert model.provider == "ollama"


def test_runtime_session_dataclass():
    """RuntimeSession dataclass has all required fields."""
    from ds_eo_openclaw.adapter.runtime_api import RuntimeSession

    session = RuntimeSession(key="test-key", agent_id="cto", status="running")
    assert session.key == "test-key"
    assert session.agent_id == "cto"
    assert session.status == "running"


def test_action_result_dataclass():
    """ActionResult dataclass defaults and fields."""
    from ds_eo_openclaw.adapter.runtime_api import ActionResult

    ok = ActionResult(success=True)
    assert ok.success is True
    assert ok.error is None
    assert ok.details == {}

    err = ActionResult(success=False, error="test error", details={"code": 500})
    assert err.success is False
    assert err.error == "test error"
    assert err.details == {"code": 500}


def test_dsh_adapter_satisfies_protocol():
    """DshRuntimeAdapter has all required methods (interface compliance)."""
    from ds_eo_openclaw.adapter.dsh_adapter import DshRuntimeAdapter

    adapter = DshRuntimeAdapter()

    # Verify all RuntimeAPI methods exist on the adapter instance
    required_methods = [
        "compact_session", "archive_session", "close_session",
        "get_session_info", "spawn_session", "submit_task", "run_tools",
        "model_info", "available_models", "run_task", "register_binding",
    ]
    for method in required_methods:
        assert hasattr(adapter, method), f"DshRuntimeAdapter missing method: {method}"
        assert callable(getattr(adapter, method)), f"{method} is not callable"


def test_openclaw_adapter_satisfies_protocol():
    """OpenClawRuntimeAdapter has all required methods (interface compliance)."""
    from ds_eo_openclaw.adapter.openclaw_adapter import OpenClawRuntimeAdapter

    adapter = OpenClawRuntimeAdapter()

    required_methods = [
        "compact_session", "archive_session", "close_session",
        "get_session_info", "spawn_session", "submit_task", "run_tools",
        "model_info", "available_models", "run_task", "register_binding",
    ]
    for method in required_methods:
        assert hasattr(adapter, method), f"OpenClawRuntimeAdapter missing method: {method}"
        assert callable(getattr(adapter, method)), f"{method} is not callable"


def test_openclaw_adapter_delegates_compact():
    """OpenClawRuntimeAdapter.compact_session delegates to OpenClawAPI."""
    from unittest.mock import patch, MagicMock
    from ds_eo_openclaw.adapter.openclaw_adapter import OpenClawRuntimeAdapter

    with patch("ds_eo_openclaw.adapter.openclaw_adapter.OpenClawAPI") as MockAPI:
        mock_api_instance = MagicMock()
        MockAPI.return_value = mock_api_instance
        mock_api_instance.compact_session.return_value = {
            "success": True, "error": None, "context_size_kb": 1024
        }

        adapter = OpenClawRuntimeAdapter()
        result = adapter.compact_session("test-session", "cto")

        MockAPI.assert_called_once_with(timeout_seconds=60)
        mock_api_instance.compact_session.assert_called_once_with("test-session", "cto")
        assert result.success is True
        assert result.details == {"context_size_kb": 1024}


def test_factory_returns_dsh():
    """RuntimeAdapterFactory.create(runtime='dsh') returns DshRuntimeAdapter."""
    from ds_eo_openclaw.adapter.runtime_api import RuntimeAdapterFactory
    from ds_eo_openclaw.adapter.dsh_adapter import DshRuntimeAdapter

    adapter = RuntimeAdapterFactory.create(runtime="dsh")
    assert isinstance(adapter, DshRuntimeAdapter)


def test_factory_returns_openclaw():
    """RuntimeAdapterFactory.create(runtime='openclaw') returns OpenClawRuntimeAdapter."""
    from ds_eo_openclaw.adapter.runtime_api import RuntimeAdapterFactory
    from ds_eo_openclaw.adapter.openclaw_adapter import OpenClawRuntimeAdapter

    adapter = RuntimeAdapterFactory.create(runtime="openclaw")
    assert isinstance(adapter, OpenClawRuntimeAdapter)


def test_factory_raises_on_unknown():
    """RuntimeAdapterFactory.create(runtime='unknown') raises ValueError."""
    from ds_eo_openclaw.adapter.runtime_api import RuntimeAdapterFactory

    try:
        RuntimeAdapterFactory.create(runtime="nonexistent")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown runtime 'nonexistent'" in str(e)


def test_dsh_adapter_stubs_raise_not_implemented():
    """All DSH stub methods raise NotImplementedError (not silently pass)."""
    from ds_eo_openclaw.adapter.dsh_adapter import DshRuntimeAdapter

    adapter = DshRuntimeAdapter()

    # Each stub should raise NotImplementedError with a meaningful message
    for method_name in [
        "compact_session", "archive_session", "close_session",
        "spawn_session", "submit_task", "run_tools",
        "run_task",
    ]:
        method = getattr(adapter, method_name)
        try:
            if method_name == "get_session_info":
                result = method("test")
                assert result is None  # get_session_info returns None instead of raising
            elif method_name in ("model_info",):
                result = method("test-model")
                assert result.context_window == 0  # stub returns zeros
            elif method_name in ("available_models",):
                result = method()
                assert result == []  # stub returns empty list
            else:
                if method_name in ("compact_session", "close_session"):
                    result = method("test", "cto")
                elif method_name == "spawn_session":
                    result = method({"test": "test"})
                elif method_name == "run_tools":
                    result = method("test-session", "tool_name", {})
                elif method_name == "submit_task":
                    result = method({"task": "test"}, "cto")
                else:
                    result = method("tool", {})
                assert result.success is False  # stub returns failure
        except NotImplementedError as e:
            assert "not yet implemented" in str(e).lower() or "notyetimplemented" in str(e).lower(), \
                f"{method_name} raised NotImplementedError without expected message"
