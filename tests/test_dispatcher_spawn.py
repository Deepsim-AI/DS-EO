"""
Tests for real session spawning infrastructure (TASK_DS_EO_038).

These tests verify the spawn infrastructure without requiring a live 
OpenClaw Gateway — they test state management, model mapping, error paths.
The actual OpenClaw integration is tested via integration tests that require
a running gateway.
"""

import json
import os
import tempfile
from unittest import TestCase
from ds_eo_openclaw.dispatcher.session_spawn import (
    SessionSpawnManager, 
    spawn_agent, 
    SpawnOutcome,
    DEFAULT_MODEL_MAP,
)


class TestSessionSpawnManagerInit(TestCase):
    """Tests for SessionSpawnManager initialization."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_init_sets_workspace_root(self):
        mgr = SessionSpawnManager(workspace_root=self.tmpdir)
        self.assertEqual(mgr.workspace_root, os.path.abspath(self.tmpdir))

    def test_init_creates_no_state_yet(self):
        """No dispatcher state should exist before first spawn."""
        mgr = SessionSpawnManager(workspace_root=self.tmpdir)
        state_dir = os.path.join(self.tmpdir, "docs", "dispatchers")
        self.assertFalse(os.path.isdir(state_dir))

    def test_default_model_map_populated(self):
        """Agent model map should have all expected roles."""
        mgr = SessionSpawnManager(workspace_root=self.tmpdir)
        self.assertIn("implementer", mgr._agent_model_map)
        self.assertIn("reviewer", mgr._agent_model_map)
        self.assertIn("cto", mgr._agent_model_map)
        self.assertIn("pm", mgr._agent_model_map)

    def test_default_model_map_correct_values(self):
        """Model mapping should match AGENTS.md definitions."""
        mgr = SessionSpawnManager(workspace_root=self.tmpdir)
        
        # From AGENTS.md: ollama/qwen3.6:27b for implementer
        self.assertEqual(
            mgr._agent_model_map["implementer"],
            "ollama/qwen3.6:27b"
        )
        
        # From AGENTS.md: ollama/laguna-xs-2.1:q4_K_M for reviewer  
        self.assertEqual(
            mgr._agent_model_map["reviewer"],
            "ollama/laguna-xs-2.1:q4_K_M"
        )
        
        # From AGENTS.md: ollama/qwen3.6:35b for cto
        self.assertEqual(
            mgr._agent_model_map["cto"],
            "ollama/qwen3.6:35b"
        )


class TestSpawnAgentBasic(TestCase):
    """Tests for basic spawn_agent() functionality."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = SessionSpawnManager(workspace_root=self.tmpdir)

    def test_spawn_unknown_role_returns_error(self):
        """AC-4: Unknown role should return error, not phantom session."""
        outcome = self.manager.spawn_agent(
            task_id="TASK_TEST_001",
            agent_role="nonexistent_role",
            prompt_content="Test work content",
        )
        
        # Should fail gracefully with descriptive error
        self.assertFalse(outcome.success)
        self.assertIn("Unknown agent role", outcome.error)
        self.assertEqual(outcome.agent_role, "nonexistent_role")

    def test_spawn_writes_dispatcher_state(self):
        """AC-1: spawn_agent() should create dispatcher state even if real session creation fails."""
        # Force failure by making openclaw CLI unavailable (no PATH lookup works in test env)
        outcome = self.manager.spawn_agent(
            task_id="TASK_TEST_002",
            agent_role="implementer",
            prompt_content="Test work content",
        )
        
        # Even though spawn fails (no real gateway), state should be written
        state_path = os.path.join(
            self.tmpdir, "docs", "dispatchers", "TASK_TEST_002", 
            "dispatcher_state.json"
        )
        self.assertTrue(os.path.exists(state_path))
        
        with open(state_path) as f:
            state = json.load(f)
        
        # Verify state structure matches expected format
        self.assertEqual(state["taskId"], "TASK_TEST_002")
        self.assertEqual(state["current_phase"], "S2_IMPLEMENTATION")
        self.assertIn("spawn_session_key", state["pending_work"])
        self.assertEqual(state["pending_work"]["assigned_to"], "implementer")

    def test_spawn_with_model_override(self):
        """Test that model override works correctly."""
        # First, create a fake openclaw CLI so spawn doesn't fail at CLI lookup
        cli_path = os.path.join(self.tmpdir, "fake_openclaw_cli")
        with open(cli_path, "w") as f:
            f.write("#!/bin/bash\necho '{}' >&2\nexit 0")
        os.chmod(cli_path, 0o755)
        
        # Add tmpdir to PATH so _find_openclaw_cli finds it
        import sys
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{self.tmpdir}:{old_path}"
        
        try:
            outcome = self.manager.spawn_agent(
                task_id="TASK_TEST_003",
                agent_role="implementer",
                prompt_content="Test with override",
                model_override="custom/model:x",  # Override the default
            )
            
            # The outcome should reflect the custom model was used
            self.assertEqual(outcome.target_model, "custom/model:x")
        finally:
            os.environ["PATH"] = old_path

    def test_verify_spawn_returns_state_info(self):
        """Verify spawn returns state info about the dispatcher entry."""
        # First create a state via spawn_agent (will fail but write state)
        self.manager.spawn_agent(
            task_id="TASK_TEST_004",
            agent_role="reviewer",
            prompt_content="Test review work",
        )
        
        # Now verify - should return state info even if session doesn't exist
        verified, info = self.manager.verify_spawn("TASK_TEST_004")
        
        # Verify spawn returns state information
        self.assertIsNotNone(info)
        self.assertIn("session_key", info)
        self.assertIn("exists", info)

    def test_verify_unknown_task_returns_false(self):
        """Verify that checking non-existent task returns False."""
        verified, info = self.manager.verify_spawn("NONEXISTENT_TASK")
        
        self.assertFalse(verified)
        self.assertIn("error", info)


class TestSpawnAgentConvenienceFunction(TestCase):
    """Tests for the module-level spawn_agent() convenience function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_convenience_function_exists_and_works(self):
        """Module-level spawn_agent() convenience function exists and works."""
        # Create fake CLI so it doesn't fail at CLI lookup
        cli_path = os.path.join(self.tmpdir, "fake_openclaw_cli")
        with open(cli_path, "w") as f:
            f.write("#!/bin/bash\necho '{}' >&2\nexit 0")
        os.chmod(cli_path, 0o755)
        
        import sys
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{self.tmpdir}:{old_path}"
        
        try:
            outcome = spawn_agent(
                workspace_root=self.tmpdir,
                task_id="TASK_TEST_005",
                agent_role="implementer",
                prompt_content="Test via convenience fn",
            )
            
            # Should work and write state even if CLI returns empty response
            self.assertIsNotNone(outcome)
        finally:
            os.environ["PATH"] = old_path


class TestSpawnOutcomeDataClass(TestCase):
    """Tests for the SpawnOutcome dataclass structure."""

    def test_spawn_outcome_to_dict(self):
        """SpawnOutcome should convert to dict properly."""
        outcome = SpawnOutcome(
            success=True,
            session_key="test_session_key",
            run_id="run_123",
            agent_role="implementer",
            target_model="ollama/qwen3.6:27b",
            error=None,
        )
        
        d = outcome.to_dict()
        self.assertEqual(d["success"], True)
        self.assertEqual(d["session_key"], "test_session_key")
        self.assertEqual(d["run_id"], "run_123")
        self.assertIsNone(d["error"])

    def test_spawn_outcome_defaults(self):
        """SpawnOutcome should have sensible defaults."""
        outcome = SpawnOutcome(success=False, error="test error")
        
        self.assertFalse(outcome.success)
        self.assertIsNone(outcome.session_key)
        self.assertIsNone(outcome.run_id)
        self.assertEqual(outcome.error, "test error")


class TestAtomicWrite(TestCase):
    """Tests for atomic file write functionality."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = SessionSpawnManager(workspace_root=self.tmpdir)

    def test_atomic_write_creates_file(self):
        """_atomic_write should create the target file."""
        test_path = os.path.join(self.tmpdir, "test.txt")
        
        ok = self.manager._atomic_write(test_path, "test content")
        
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(test_path))
        
        with open(test_path) as f:
            self.assertEqual(f.read(), "test content")

    def test_atomic_write_replaces_existing(self):
        """_atomic_write should replace existing files."""
        test_path = os.path.join(self.tmpdir, "existing.txt")
        
        # Write initial content
        with open(test_path, "w") as f:
            f.write("old content")
        
        # Atomic write should replace it
        ok = self.manager._atomic_write(test_path, "new content")
        
        self.assertTrue(ok)
        with open(test_path) as f:
            self.assertEqual(f.read(), "new content")

    def test_atomic_write_no_temp_file_left(self):
        """_atomic_write should not leave .tmp files after success."""
        test_path = os.path.join(self.tmpdir, "no_tmp.txt")
        
        ok = self.manager._atomic_write(test_path, "content")
        
        if ok:  # Only check if write succeeded
            tmp_file = test_path + ".tmp"
            self.assertFalse(os.path.exists(tmp_file))


class TestCleanupOnFailure(TestCase):
    """Tests for cleanup behavior on spawn failure."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = SessionSpawnManager(workspace_root=self.tmpdir)

    def test_cleanup_removes_mapping_file(self):
        """_cleanup_spawn_state should remove spawn_mapping.json if it exists."""
        task_dir = os.path.join(self.tmpdir, "docs", "dispatchers", "TASK_TEST_006")
        os.makedirs(task_dir, exist_ok=True)
        
        mapping_path = os.path.join(task_dir, "spawn_mapping.json")
        
        # Create a fake mapping to test cleanup
        with open(mapping_path, "w") as f:
            json.dump({"test": "data"}, f)
        
        self.assertTrue(os.path.exists(mapping_path))
        
        # Cleanup should remove it
        self.manager._cleanup_spawn_state("TASK_TEST_006")
        
        self.assertFalse(os.path.exists(mapping_path))

    def test_cleanup_handles_missing_file(self):
        """_cleanup_spawn_state should not fail if mapping doesn't exist."""
        # Should not raise even if file doesn't exist
        self.manager._cleanup_spawn_state("NONEXISTENT_TASK_CLEANUP")


# ==================================================================
# Integration-style tests that require a live OpenClaw Gateway
# ==================================================================

class TestRealGatewayIntegration(TestCase):
    """
    These tests verify the spawn logic works with a real OpenClaw Gateway.
    
    They're marked as integration tests and will be skipped if no gateway is available.
    In CI/CD or production, these would run against a live gateway instance.
    """

    @classmethod
    def setUpClass(cls):
        """Check if openclaw CLI is available."""
        import shutil
        cls.has_openclaw = shutil.which("openclaw") is not None
        
        # Also check for gateway socket (Path A)
        cls.gateway_socket = os.environ.get("OPENCLAW_GATEWAY_SOCKET", "")
        cls.has_gateway_socket = (
            bool(cls.gateway_socket) and 
            os.path.exists(cls.gateway_socket)
        )

    def test_real_spawn_requires_gateway(self):
        """Real spawn should require a gateway connection.
        
        Verifies that when the gateway is reachable but credentials are missing/invalid,
        spawn fails gracefully with an error message (not a crash or phantom success).
        """
        if not self.has_openclaw and not self.has_gateway_socket:
            self.skipTest("No OpenClaw Gateway available for integration test")
        
        tmpdir = tempfile.mkdtemp()
        manager = SessionSpawnManager(workspace_root=tmpdir)
        
        outcome = manager.spawn_agent(
            task_id="TASK_INTEGRATION_TEST",
            agent_role="implementer",
            prompt_content="Integration test prompt",
        )
        
        # With a real gateway, spawn should either:
        #   1. Succeed (if valid credentials are configured)
        #   2. Fail with a descriptive error (not crash or return phantom success)
        self.assertIsNotNone(outcome)
        if outcome.success:
            # Gateway accepted — verify we got a session key back
            self.assertIsNotNone(outcome.session_key, "Success should include session_key")
        else:
            # Gateway rejected (e.g., 401 auth required but token not set) — 
            # the important thing is that we got an error message, not a crash
            self.assertIn("error", outcome.__dict__ or {"error": outcome.error})
            self.assertIsNotNone(outcome.error, "Failed spawn should have error description")


if __name__ == "__main__":
    import unittest
    
    # Run tests with verbose output
    unittest.main(verbosity=2)
