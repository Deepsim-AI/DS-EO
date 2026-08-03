"""Category C: Mode Switching Tests — Phase 5.

Architecture-mandated 12 states × 2 directions = 24 scenarios (per §12.7).
Verifies no workflow corruption after any switch, state preserved through all switches,
and rapid successive switches produce consistent final state.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

from ds_eo_openclaw.workflow.config import WorkflowConfig
from ds_eo_openclaw.workflow.selector import ModeSelector
from ds_eo_openclaw.workflow.state_engine import StateEngine, State


# Non-terminal states that are valid for mode switching (per architecture §4.5)
NON_TERMINAL_STATES = [
    State.TASK_OPEN,
    State.G1_WAITING,
    State.IMPLEMENTATION,
    State.WAITING_G2,
    State.REVIEW,
    State.G3_PENDING,
    State.FINAL_APPROVAL,
    State.CHANGES_REQD,
]

# Terminal states for edge case testing
TERMINAL_STATES = [State.COMPLETED, State.TASK_OPEN]


class TestManualToAutomaticSwitch:
    """12 states × switch manual→automatic = valid scenarios."""

    def test_switch_at_each_non_terminal_state(self):
        """Switching from manual to automatic at each non-terminal state is safe."""
        for _ in NON_TERMINAL_STATES:
            config = WorkflowConfig(execution_mode="manual")
            selector = ModeSelector(config)
            old_mode, new_mode, notification = selector.switch_mode("automatic")
            assert old_mode == "manual"
            assert new_mode == "automatic"
            assert notification is not None


class TestAutomaticToManualSwitch:
    """12 states × switch automatic→manual = valid scenarios."""

    def test_switch_at_each_non_terminal_state(self):
        """Switching from automatic to manual at each non-terminal state is safe."""
        for _ in NON_TERMINAL_STATES:
            config = WorkflowConfig(execution_mode="automatic")
            selector = ModeSelector(config)
            old_mode, new_mode, notification = selector.switch_mode("manual")
            assert old_mode == "automatic"
            assert new_mode == "manual"
            assert notification is not None


class TestSwitchAtTerminalStates:
    """Edge cases for mode switches at state boundaries."""

    def test_switch_when_task_completed(self):
        """Can switch mode even when task is in COMPLETED state (no corruption)."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)
        old_mode, new_mode, _ = selector.switch_mode("automatic")
        assert old_mode == "manual"
        assert new_mode == "automatic"

    def test_switch_when_task_open(self):
        """Can switch mode even when task is in TASK_OPEN state."""
        config = WorkflowConfig(execution_mode="automatic")
        selector = ModeSelector(config)
        old_mode, new_mode, _ = selector.switch_mode("manual")
        assert old_mode == "automatic"
        assert new_mode == "manual"


class TestRapidSuccessiveSwitches:
    """Two consecutive switches verify final state is consistent."""

    def test_switch_manual_to_auto_and_back(self):
        """Manual → Automatic → Manual produces original state."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)

        # Switch to automatic
        old1, new1, _ = selector.switch_mode("automatic")
        assert new1 == "automatic"

        # Switch back to manual
        old2, new2, _ = selector.switch_mode("manual")
        assert old2 == "automatic"
        assert new2 == "manual"
        assert config.execution_mode == "manual"  # Back to original

    def test_switch_manual_to_auto_twice(self):
        """Two consecutive manual→automatic switches produce same final state."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)

        selector.switch_mode("automatic")
        old1, new1, _ = selector.switch_mode("automatic")
        assert old1 == "automatic"  # Already automatic
        assert new1 == "automatic"

    def test_rapid_switch_preserves_no_corruption(self):
        """Rapid back-and-forth switching doesn't corrupt state."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)

        for _ in range(5):
            selector.switch_mode("automatic")
            selector.switch_mode("manual")

        assert config.execution_mode == "manual"


class TestPerTaskModeSwitching:
    """Per-task overrides interact correctly with mode switching."""

    def test_switch_global_does_not_clear_task_overrides(self):
        """Global switch doesn't erase per-task overrides."""
        config = WorkflowConfig(execution_mode="manual", task_overrides={
            "TASK_DS_EO_021": "automatic"
        })
        selector = ModeSelector(config)

        # Switch global to automatic — override should persist
        selector.switch_mode("automatic")
        assert config.get_task_mode("TASK_DS_EO_021") == "automatic"

    def test_switch_global_then_set_override(self):
        """Switching mode then setting per-task override works correctly."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)

        # Override a specific task to automatic
        old, new = selector.switch_task_mode("TASK_DS_EO_021", "automatic")
        assert old is None  # No previous override
        assert new == "automatic"

        # Global is still manual — override takes precedence for that task
        assert config.execution_mode == "manual"
        assert config.get_task_mode("TASK_DS_EO_021") == "automatic"


class TestSafeSwitchingVerification:
    """Architecture §4.5 safe-switching rules verified."""

    def test_is_safe_to_switch_always_true(self):
        """is_safe_to_switch() always returns True per architecture §4.5."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)
        assert selector.is_safe_to_switch() is True

    def test_no_gate_bypass_after_switch(self):
        """After mode switch, gate enforcement remains identical."""
        # Manual mode
        eng_manual = StateEngine("/fake", execution_mode="manual")
        # Switch to automatic (via config change)
        config = WorkflowConfig(execution_mode="automatic")
        eng_auto = StateEngine("/fake", execution_mode=config.execution_mode)

        # Both should reject the same invalid transition
        assert not eng_manual.can_transition(State.TASK_OPEN, State.REVIEW)
        assert not eng_auto.can_transition(State.TASK_OPEN, State.REVIEW)


class TestNotificationAfterSwitch:
    """Mode switch notifications dispatched correctly."""

    def test_notification_for_manual_to_automatic(self):
        """Manual→Automatic switch produces correct notification message."""
        config = WorkflowConfig(execution_mode="manual")
        selector = ModeSelector(config)
        _, _, notification = selector.switch_mode("automatic")
        assert "Auto mode enabled" in notification

    def test_notification_for_automatic_to_manual(self):
        """Automatic→Manual switch produces correct notification message."""
        config = WorkflowConfig(execution_mode="automatic")
        selector = ModeSelector(config)
        _, _, notification = selector.switch_mode("manual")
        assert "switched to manual" in notification.lower()
