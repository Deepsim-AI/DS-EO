"""
Test: CapabilityAssessor auto-detection logic.

Phase A deliverable 8 of TASK_DS_EO_043.
"""
import pytest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dispatcher.execution_strategy.capability_assessor import CapabilityAssessor
from dispatcher.execution_strategy.constants import Strategy


class TestCapabilityAssessor:
    """Test auto-detection decision matrix."""

    @patch.object(CapabilityAssessor, 'detect_total_memory', return_value=61.2)
    @patch.object(CapabilityAssessor, 'detect_gpu_vram', return_value=None)
    @patch.object(CapabilityAssessor, 'detect_memory_type', return_value='unified')
    @patch.object(CapabilityAssessor, 'get_configured_model_sizes', return_value={
        'ollama/qwen3.6:35b': 23.0,
        'ollama/ornith:35b': 21.0,
    })
    @patch.object(CapabilityAssessor, 'count_active_loaded_models', return_value=2)
    @patch.object(CapabilityAssessor, 'count_distinct_agent_models', return_value=4)
    def test_unified_memory_favors_sequential(self, mock_distinct, mock_active,
                                               mock_sizes, mock_mem_type, mock_vram, mock_mem):
        report = CapabilityAssessor.assess()
        assert report.strategy == "sequential"
        assert report.confidence >= 0.90
        # Should mention unified memory in reason
        assert "unified" in report.reason.lower() or "sequential" in report.reason.lower()

    @patch.object(CapabilityAssessor, 'detect_total_memory', return_value=64.0)
    @patch.object(CapabilityAssessor, 'detect_gpu_vram', return_value=12.0)
    @patch.object(CapabilityAssessor, 'detect_memory_type', return_value='discrete')
    @patch.object(CapabilityAssessor, 'get_configured_model_sizes', return_value={
        'ollama/qwen3.6:35b': 23.0,
        'ollama/ornith:35b': 21.0,
    })
    @patch.object(CapabilityAssessor, 'count_active_loaded_models', return_value=0)
    @patch.object(CapabilityAssessor, 'count_distinct_agent_models', return_value=2)
    def test_discrete_gpu_enables_concurrent(self, mock_distinct, mock_active,
                                              mock_sizes, mock_mem_type, mock_vram, mock_mem):
        report = CapabilityAssessor.assess()
        assert report.strategy == "concurrent"
        assert report.confidence >= 0.80

    @patch.object(CapabilityAssessor, 'detect_total_memory', return_value=16.0)
    @patch.object(CapabilityAssessor, 'detect_gpu_vram', return_value=None)
    @patch.object(CapabilityAssessor, 'detect_memory_type', return_value='unknown')
    @patch.object(CapabilityAssessor, 'get_configured_model_sizes', return_value={})
    @patch.object(CapabilityAssessor, 'count_active_loaded_models', return_value=0)
    @patch.object(CapabilityAssessor, 'count_distinct_agent_models', return_value=1)
    def test_constrained_falls_back_sequential(self, mock_distinct, mock_active,
                                                mock_sizes, mock_mem_type, mock_vram, mock_mem):
        report = CapabilityAssessor.assess()
        assert report.strategy == "sequential"

    def test_parse_size_gb_handles_formats(self):
        # Test actual parsing logic for different formats
        cases = [
            ("23 GB", 23.0),
            ("274 MB", 0.2676),
            ("21 GB", 21.0),
            ("", 0.0),
            ("512 KB", 0.000488),
            ("10", 10.0),  # bare number assumes GB
        ]
        for size_str, expected in cases:
            actual = CapabilityAssessor._parse_size_gb(size_str)
            assert pytest.approx(actual, rel=1e-3) == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
