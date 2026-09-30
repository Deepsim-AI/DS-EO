"""Tests for DshHttpClient (Phase 6 HTTP client infrastructure).

These tests validate the DSH HTTP client wiring without requiring a live DSH API.
"""

import sys
import os
from unittest.mock import patch, MagicMock
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ds_eo_openclaw"))

from ds_eo_openclaw.adapter.dsh_http_client import DshHttpClient
from ds_eo_openclaw.adapter.dsh_adapter import DshRuntimeAdapter


class TestDshHttpClient:
    """Test DSH HTTP client behavior."""

    def test_post_success(self):
        """HTTP POST → parsed response dict on success."""
        client = DshHttpClient(base_url="https://dsh.example.com/api", auth_token="test-token")
        
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"status": "ok"}).encode("utf-8")
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            result = client.post("/sessions/key/compact", body={"session_key": "key"})
            
            assert result == {"status": "ok"}, f"Expected parsed dict, got {result}"
            mock_urlopen.assert_called_once()

    def test_post_timeout(self):
        """HTTP POST timeout → None (caller handles error)."""
        client = DshHttpClient(base_url="https://dsh.example.com/api")
        
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            result = client.post("/sessions/key/compact", body={"session_key": "key"})
            
            assert result is None, f"Expected None on timeout, got {result}"

    def test_post_http_error(self):
        """HTTP 500 error → None (caller handles error)."""
        client = DshHttpClient(base_url="https://dsh.example.com/api")
        
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            "https://dsh.example.com/api/sessions/key/compact",
            500, "Internal Server Error", {}, None)):
            result = client.post("/sessions/key/compact", body={"session_key": "key"})
            
            assert result is None, f"Expected None on HTTP error, got {result}"

    def test_get_success(self):
        """HTTP GET → parsed response dict on success."""
        client = DshHttpClient(base_url="https://dsh.example.com/api")
        
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"status": "active", "context_size_bytes": 4096}).encode("utf-8")
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.get("/sessions/my-session")
            
            assert result == {"status": "active", "context_size_bytes": 4096}

    def test_get_session_info_dsh_path(self):
        """DSH get_session_info returns RuntimeSession when API available."""
        # Use a mock DSH client directly
        from ds_eo_openclaw.adapter.dsh_adapter import DshRuntimeAdapter
        
        # Patch the HTTP client's get method directly via monkeypatch
        from ds_eo_openclaw.adapter.dsh_http_client import DshHttpClient
        original_init = DshHttpClient.__init__
        
        def mock_init(self, base_url="", auth_token=None, timeout=30):
            original_init(self, base_url, auth_token, timeout)
            self._is_available = True
        
        with patch.object(DshHttpClient, '__init__', mock_init):
            with patch.object(DshHttpClient, 'get', return_value={
                "status": "active",
                "context_size_bytes": 8192,
                "turn_count": 42,
                "last_turn_time": "2026-09-29T22:00:00Z",
            }):
                adapter = DshRuntimeAdapter(base_url="https://dsh.example.com/api")
                result = adapter.get_session_info("test-session")
        
        assert result is not None, "Expected RuntimeSession, got None"
        assert result.key == "test-session"
        assert result.status == "running"  # normalized from "active"
        assert result.context_size_bytes == 8192
        assert result.turn_count == 42

    def test_get_session_info_fallback(self):
        """DSH unavailable → None (fallback path)."""
        adapter = DshRuntimeAdapter()  # no base_url
        
        result = adapter.get_session_info("test-session")
        
        assert result is None, "Expected None when DSH unavailable"

    def test_compact_session_dsh_path(self):
        """DSH compact_session succeeds when API available."""
        from ds_eo_openclaw.adapter.dsh_adapter import DshRuntimeAdapter
        
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.post.return_value = {
            "success": True,
            "context_size_kb": 128,
            "tokens_compacted": 5000,
        }
        
        adapter = DshRuntimeAdapter(base_url="https://dsh.example.com/api")
        adapter._client = mock_client
        
        result = adapter.compact_session("test-session")
        
        assert result.success is True
        assert result.details.get("context_size_kb") == 128
        assert result.details.get("tokens_compacted") == 5000

    def test_close_session_dsh_path(self):
        """DSH close_session succeeds when API available."""
        from ds_eo_openclaw.adapter.dsh_adapter import DshRuntimeAdapter
        
        mock_client = MagicMock()
        mock_client.is_available.return_value = True
        mock_client.delete.return_value = True
        
        adapter = DshRuntimeAdapter(base_url="https://dsh.example.com/api")
        adapter._client = mock_client
        
        result = adapter.close_session("test-session")
        
        assert result.success is True

    def test_model_info_dsh_fallback(self):
        """model_info returns RuntimeModel even when API unavailable."""
        adapter = DshRuntimeAdapter()  # no base_url
        
        result = adapter.model_info("ollama/qwen3.6:35b")
        
        assert result is not None
        assert result.id == "ollama/qwen3.6:35b"
        assert result.provider == "dsh"

    def test_client_is_available_with_url(self):
        """is_available returns True when base_url configured."""
        client = DshHttpClient(base_url="https://example.com/api")
        assert client.is_available() is True

    def test_client_is_unavailable_without_url(self):
        """is_available returns False when no base_url."""
        client = DshHttpClient()
        assert client.is_available() is False


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
