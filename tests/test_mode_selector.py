"""Tests for DS-EO Phase 3 — User-Facing Mode Selector.

Covers acceptance criteria from TASK_DS_EO_022:
  - Config validation (valid inputs, invalid inputs, defaults)
  - Mode switch atomicity (previous/new returned, audit trail)
  - Per-task override precedence over global default
  - Notification lookup for all §6.3 messages
  - State engine integration with config on init
"""

import os
import tempfile
import unittest

from ds_eo_openclaw.workflow.config import WorkflowConfig, DEFAULT_CONFIG
from ds_eo_openclaw.workflow.selector import ModeSelector, create_selector
from ds_eo_openclaw.workflow.notifications import (
    AUTO_MODE_NOTIFICATIONS, MODE_NOTIFICATIONS,
    get_mode_switch_notification, get_auto_mode_notification,
)
from ds_eo_openclaw.workflow.state_engine import StateEngine, State


# --------------------------------------------------------------------------- #
# Config Validation Tests
# --------------------------------------------------------------------------- #

class TestWorkflowConfigValidation(unittest.TestCase):
    """Verify config accepts valid modes and rejects invalid ones."""

    def test_default_mode_is_manual(self):
        """Default WorkflowConfig has execution_mode='manual'."""
        config = WorkflowConfig()
        self.assertEqual(config.execution_mode, "manual")

    def test_explicit_automatic_mode(self):
        """Can construct with 'automatic' mode."""
        config = WorkflowConfig(execution_mode="automatic")
        self.assertEqual(config.execution_mode, "automatic")

    def test_invalid_mode_raises_value_error(self):
        """Invalid execution_mode raises ValueError (not silent default)."""
        for invalid in ("", "MANUAL", "auto", 123, None):
            with self.assertRaises(ValueError):
                WorkflowConfig(execution_mode=invalid)

    def test_switch_returns_previous_mode(self):
        """switch() returns the previous mode before changing."""
        config = WorkflowConfig()
        old = config.switch("automatic")
        self.assertEqual(old, "manual")
        self.assertEqual(config.execution_mode, "automatic")

    def test_switch_invalid_raises_value_error(self):
        """Switch to invalid mode raises ValueError; state unchanged."""
        config = WorkflowConfig()
        with self.assertRaises(ValueError):
            config.switch("invalid")
        # State should not have been corrupted
        self.assertEqual(config.execution_mode, "manual")


# --------------------------------------------------------------------------- #
# Per-Task Override Tests
# --------------------------------------------------------------------------- #

class TestPerTaskOverrides(unittest.TestCase):
    """Verify per-task overrides take precedence over global default."""

    def test_get_task_mode_returns_global_when_no_override(self):
        """No override → returns global mode."""
        config = WorkflowConfig(execution_mode="manual")
        self.assertEqual(config.get_task_mode("TASK_DS_EO_021"), "manual")

    def test_override_takes_precedence_over_global(self):
        """Per-task override wins over global default."""
        config = WorkflowConfig(execution_mode="manual", task_overrides={
            "TASK_DS_EO_021": "automatic"
        })
        self.assertEqual(config.get_task_mode("TASK_DS_EO_021"), "automatic")

    def test_set_task_override_returns_previous(self):
        """set_task_override() returns previous value (or None)."""
        config = WorkflowConfig(execution_mode="manual")
        # First set: no previous → None
        old = config.set_task_override("TASK_DS_EO_021", "automatic")
        self.assertIsNone(old)

        # Second set: previous was 'automatic'
        old = config.set_task_override("TASK_DS_EO_021", "manual")
        self.assertEqual(old, "automatic")

    def test_remove_task_override_reverts_to_global(self):
        """remove_task_override() reverts to global default."""
        config = WorkflowConfig(execution_mode="manual", task_overrides={
            "TASK_DS_EO_021": "automatic"
        })
        removed = config.remove_task_override("TASK_DS_EO_021")
        self.assertTrue(removed)
        self.assertEqual(config.get_task_mode("TASK_DS_EO_021"), "manual")

    def test_remove_nonexistent_override_returns_false(self):
        """Removing a non-existent override returns False."""
        config = WorkflowConfig()
        removed = config.remove_task_override("NONEXISTENT_TASK")
        self.assertFalse(removed)


# --------------------------------------------------------------------------- #
# Mode Selector Tests
# --------------------------------------------------------------------------- #

class TestModeSelector(unittest.TestCase):
    """Verify mode selector provides safe switching with audit trail."""

    def test_switch_mode_returns_tuple(self):
        """switch_mode() returns (old_mode, new_mode, notification)."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)
        result = selector.switch_mode("automatic")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "manual")   # previous
        self.assertEqual(result[1], "automatic") # new

    def test_switch_mode_updates_config(self):
        """switch_mode() actually changes the config state."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)
        selector.switch_mode("automatic")
        self.assertEqual(config.execution_mode, "automatic")

    def test_switch_task_mode_returns_tuple(self):
        """switch_task_mode() returns (previous_override_or_None, new_mode)."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)
        result = selector.switch_task_mode("TASK_DS_EO_021", "automatic")
        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0])  # no previous override
        self.assertEqual(result[1], "automatic")

    def test_switch_task_mode_updates_config(self):
        """switch_task_mode() actually sets the per-task override."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)
        selector.switch_task_mode("TASK_DS_EO_021", "automatic")
        self.assertEqual(
            config.get_task_mode("TASK_DS_EO_021"),
            "automatic"
        )

    def test_is_safe_to_switch_returns_true(self):
        """is_safe_to_switch() always returns True per §4.5 architecture rules."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)
        self.assertTrue(selector.is_safe_to_switch())

    def test_invalid_mode_raises_value_error(self):
        """switch_mode() with invalid mode raises ValueError."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)
        with self.assertRaises(ValueError):
            selector.switch_mode("invalid")

    def test_no_gate_bypass_in_any_mode(self):
        """Mode change does not affect transition validation (gates preserved)."""
        from ds_eo_openclaw.workflow.state_engine import StateEngine, State

        # Manual mode
        eng_manual = StateEngine("/fake", execution_mode="manual")
        self.assertFalse(eng_manual.can_transition(State.TASK_OPEN, State.REVIEW))

        # Automatic mode — same transition still invalid
        eng_auto = StateEngine("/fake", execution_mode="automatic")
        self.assertFalse(eng_auto.can_transition(State.TASK_OPEN, State.REVIEW))


# --------------------------------------------------------------------------- #
# Notification Tests
# --------------------------------------------------------------------------- #

class TestNotifications(unittest.TestCase):
    """Verify all §6.3 notifications are defined with exact wording."""

    def test_all_7_auto_mode_notifications_defined(self):
        """All 7 state notifications from §6.3 must be present."""
        expected_states = {
            "G1_WAITING", "REVIEW", "G3_PENDING", "COMPLETED",
            "CHANGES_REQD", "BLOCKED", "STALLED"
        }
        actual_states = set(AUTO_MODE_NOTIFICATIONS.keys())
        self.assertEqual(actual_states, expected_states)

    def test_both_mode_switch_notifications_defined(self):
        """Both directions of mode switch must have notifications."""
        expected_keys = {("manual", "automatic"), ("automatic", "manual")}
        actual_keys = set(MODE_NOTIFICATIONS.keys())
        self.assertEqual(actual_keys, expected_keys)

    def test_auto_mode_notification_content_g1_waiting(self):
        """G1_WAITING notification matches §6.3 exactly."""
        self.assertEqual(
            AUTO_MODE_NOTIFICATIONS["G1_WAITING"],
            "Plan submitted for review"
        )

    def test_auto_mode_notification_content_completed(self):
        """COMPLETED notification matches §6.3 exactly."""
        self.assertEqual(
            AUTO_MODE_NOTIFICATIONS["COMPLETED"],
            "Task completed, cleanup in progress"
        )

    def test_auto_mode_notification_content_blocked(self):
        """BLOCKED notification matches §6.3 exactly."""
        self.assertEqual(
            AUTO_MODE_NOTIFICATIONS["BLOCKED"],
            "BLOCKER: [details]"
        )

    def test_mode_switch_notification_manual_to_automatic(self):
        """Manual → Automatic switch notification matches §6.3."""
        expected = "Auto mode enabled — PM will auto-advance eligible transitions"
        self.assertEqual(
            MODE_NOTIFICATIONS[("manual", "automatic")],
            expected
        )

    def test_mode_switch_notification_automatic_to_manual(self):
        """Automatic → Manual switch notification matches §6.3."""
        expected = "Mode switched to manual — all transitions require explicit action"
        self.assertEqual(
            MODE_NOTIFICATIONS[("automatic", "manual")],
            expected
        )

    def test_get_mode_switch_notification_returns_message(self):
        """Convenience function returns correct notification message."""
        msg = get_mode_switch_notification("manual", "automatic")
        self.assertIsNotNone(msg)
        self.assertIn("Auto mode", msg)

    def test_get_auto_mode_notification_returns_message(self):
        """Convenience function returns correct state notification."""
        msg = get_auto_mode_notification("G1_WAITING")
        self.assertEqual(msg, "Plan submitted for review")


# --------------------------------------------------------------------------- #
# Integration Tests — State Engine with Config
# --------------------------------------------------------------------------- #

class TestStateEngineConfigIntegration(unittest.TestCase):
    """Verify state engine works correctly with Phase 3 config."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_state_engine_reads_execution_mode_from_config(self):
        """StateEngine accepts execution_mode from WorkflowConfig.get_task_mode()."""
        config = WorkflowConfig(execution_mode="automatic", task_overrides={
            "TASK_DS_EO_021": "manual"
        })
        mode = config.get_task_mode("TASK_DS_EO_021")  # → "manual" (override)

        eng = StateEngine(self.tmpdir, execution_mode=mode)
        self.assertEqual(eng.execution_mode, "manual")

    def test_state_engine_manual_mode_no_auto_advance(self):
        """Manual mode still returns None for auto_advance() — zero regression."""
        config = WorkflowConfig(execution_mode="manual")
        eng = StateEngine(self.tmpdir, execution_mode=config.execution_mode)
        self.assertIsNone(eng.auto_advance())

    def test_state_engine_automatic_mode_auto_advances(self):
        """Automatic mode still auto-advances — zero regression."""
        config = WorkflowConfig(execution_mode="automatic")
        eng = StateEngine(self.tmpdir, execution_mode=config.execution_mode)
        result = eng.auto_advance()  # S0 → G1_WAITING
        self.assertIsNotNone(result)


# --------------------------------------------------------------------------- #
# Factory Function Tests
# --------------------------------------------------------------------------- #

class TestCreateSelector(unittest.TestCase):
    """Verify create_selector factory function works correctly."""

    def test_create_with_default_config(self):
        """create_selector(None) uses DEFAULT_CONFIG."""
        selector = create_selector()
        self.assertEqual(selector.config, DEFAULT_CONFIG)

    def test_create_with_custom_config(self):
        """create_selector(config) uses the provided config."""
        custom = WorkflowConfig(execution_mode="automatic")
        selector = create_selector(custom)
        self.assertIs(selector.config, custom)


if __name__ == "__main__":
    unittest.main()
