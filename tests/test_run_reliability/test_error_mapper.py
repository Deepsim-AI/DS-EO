# TASK_DS_EO_040 — Tests for Error Mapper Module

import pytest

from ds_eo_openclaw.run_reliability.error_mapper import (
    ERROR_PATTERNS,
    map_raw_message_to_classification,
    format_structured_error,
)
from ds_eo_openclaw.run_reliability.reconciler import ErrorClassification


class TestErrorMapper:
    """Tests for the error mapper's pattern matching and formatting."""

    def test_all_patterns_have_required_fields(self):
        """Every defined pattern must have name, classification, patterns list, description."""
        for p in ERROR_PATTERNS:
            assert p.name, f"Pattern missing name"
            assert p.classification, f"Pattern {p.name} missing classification"
            assert len(p.patterns) > 0, f"Pattern {p.name} has no patterns"
            assert p.description, f"Pattern {p.name} missing description"

    def test_map_no_active_run(self):
        cls, desc = map_raw_message_to_classification("no active run", False, True)
        assert cls == ErrorClassification.RUN_STATE_MISMATCH

    def test_map_orphaned(self):
        cls, _ = map_raw_message_to_classification("orphaned run detected during dispatch", None, False)
        assert cls == ErrorClassification.ORPHANED_RUN

    def test_map_compaction(self):
        cls, _ = map_raw_message_to_classification("compaction failed: context overflow", None, True)
        assert cls == ErrorClassification.COMPACTION_ABORT_FAILURE

    def test_map_abort_finalization(self):
        cls, _ = map_raw_message_to_classification(
            "Agent reply is already finalizing", None, True
        )
        assert cls == ErrorClassification.ABORT_DURING_FINALIZATION

    def test_map_invalid_run_id(self):
        cls, _ = map_raw_message_to_classification("invalid run id xyz-123", None, False)
        assert cls == ErrorClassification.INVALID_RUN_ID

    def test_map_irrecoverable(self):
        cls, _ = map_raw_message_to_classification(
            "irrecoverable error: corrupt state detected", None, False
        )
        assert cls == ErrorClassification.IRRECOVERABLE_ERROR

    def test_state_context_override(self):
        """When no pattern matches but state context indicates mismatch → RUN_STATE_MISMATCH."""
        cls, _ = map_raw_message_to_classification(
            "some random error", runtime_state_idle=True, control_plane_active=True
        )
        assert cls == ErrorClassification.RUN_STATE_MISMATCH

    def test_unknown_fallback(self):
        """No pattern match + no state context → UNKNOWN."""
        cls, desc = map_raw_message_to_classification("xyz123", None, False)
        assert cls == ErrorClassification.UNKNOWN

    def test_format_structured_error(self):
        formatted = format_structured_error(
            ErrorClassification.RUN_STATE_MISMATCH,
            "no active run",
        )
        assert "[ERROR CLASSIFIED]" in formatted
        assert "RUN_STATE_MISMATCH" in formatted
        assert "no active run" in formatted

    def test_format_with_custom_description(self):
        formatted = format_structured_error(
            ErrorClassification.ORPHANED_RUN,
            "orphaned session",
            description="Custom override",
        )
        assert "Custom override" in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
