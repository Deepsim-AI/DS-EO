# TASK_DS_EO_040 — Tests for Recovery Protocol Module

import pytest

from ds_eo_openclaw.run_reliability.recovery_protocol import (
    RecoveryAction,
    get_recovery_steps,
    get_recovery_procedure,
    is_recoverable,
    format_recovery_procedure,
)


class TestRecoveryProtocol:
    """Tests for the recovery protocol module."""

    def test_orphaned_run_has_steps(self):
        steps = get_recovery_steps("orphaned_run")
        assert steps is not None
        assert len(steps) >= 2
        assert any("Clear" in s.action or "clear" in s.action.lower() for s in steps)

    def test_engine_ahead_has_steps(self):
        steps = get_recovery_steps("engine_ahead")
        assert steps is not None
        assert len(steps) >= 1

    def test_timeout_in_progress_is_automated(self):
        proc = get_recovery_procedure("timeout_in_progress")
        assert proc.is_automated is True

    def test_invalid_run_id_has_steps(self):
        steps = get_recovery_steps("invalid_run_id")
        assert steps is not None
        assert len(steps) >= 2

    def test_compaction_abort_failure_exists(self):
        steps = get_recovery_steps("compaction_abort_failure")
        assert steps is not None
        assert len(steps) >= 3

    def test_is_recoverable_true_for_known(self):
        for key in ["orphaned_run", "engine_ahead", "timeout_in_progress", "invalid_run_id", "compaction_abort_failure"]:
            assert is_recoverable(key) is True, f"Expected {key} to be recoverable"

    def test_is_recoverable_false_for_unknown(self):
        assert is_recoverable("nonexistent_diagnosis") is False

    def test_format_recovery_procedure_returns_string(self):
        formatted = format_recovery_procedure("orphaned_run")
        assert formatted is not None
        assert "Orphaned Run" in formatted or "orphaned" in formatted.lower()
        assert "Steps:" in formatted

    def test_format_unknown_diagnosis(self):
        assert format_recovery_procedure("nonexistent") is None

    def test_orphaned_steps_have_ordering(self):
        steps = get_recovery_steps("orphaned_run")
        orders = [s.order for s in steps]
        assert orders == sorted(orders), "Steps must be ordered"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
