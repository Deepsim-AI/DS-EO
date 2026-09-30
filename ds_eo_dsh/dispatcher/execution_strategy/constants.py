"""
Execution Strategy — Constants, Enums, and Type Definitions.

Phase A deliverable 2 of TASK_DS_EO_043.
Source of truth: CTO_PLAN.md §5.1–§5.6.

Defines the strategy taxonomy, model state machine states, capability
assessment thresholds, and error codes used across all execution strategies.
"""

from enum import Enum


# ============================================================================
# Strategy Taxonomy (CTO_PLAN.md §2)
# ============================================================================

class Strategy(str, Enum):
    """Supported execution strategies."""
    CONCURRENT = "concurrent"
    SEQUENTIAL = "sequential"
    SHARED_MODEL = "shared_model"


# ============================================================================
# Model State Machine States (CTO_PLAN.md §3 + §5.3)
# ============================================================================

class ModelState(str, Enum):
    """Lifecycle states for a model within the sequential strategy."""
    UNLOADED = "UNLOADED"
    LOAD_REQUIRED = "LOAD_REQUIRED"
    LOADING = "LOADING"
    READY = "READY"
    BUSY = "BUSY"
    UNLOADING = "UNLOADING"
    ERROR = "ERROR"


# ============================================================================
# Model Lifecycle Error Codes (CTO_PLAN.md §5.3)
# ============================================================================

class ModelStateError(Exception):
    """Typed error for model lifecycle failures."""

    MODEL_LOAD_TIMEOUT = "MODEL_LOAD_TIMEOUT"
    INSUFFICIENT_MEMORY = "INSUFFICIENT_MEMORY"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    UNLOAD_FAILURE = "UNLOAD_FAILURE"
    CONCURRENT_TRANSITION = "CONCURRENT_TRANSITION"
    API_ERROR = "API_ERROR"
    READY_CHECK_FAILURE = "READY_CHECK_FAILURE"

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ============================================================================
# Thresholds and Configuration Constants (CTO_PLAN.md §4.1)
# ============================================================================

MODEL_LOAD_TIMEOUT_SECONDS = 60
"""Maximum seconds to wait for a model to load before timing out."""

UNLOAD_POLL_INTERVAL_MS = 500
"""Poll interval (ms) when waiting for model unload to complete."""

MIN_FREE_RAM_GB = 8
"""Minimum free RAM in GB below which we refuse to load a new model."""

# Auto-detection thresholds from CTO_PLAN.md §4.1 decision matrix
TOTAL_MEMORY_CONCURRENT_THRESHOLD_GB = 32
"""Total system memory (GB) — below this, concurrent is disqualified."""

UNIFIED_MEMORY_CONCURRENT_THRESHOLD_GB = 64
"""Unified memory threshold — >= 64GB may support two ~20GB models safely."""

MODEL_SIZE_VRAM_RATIO_THRESHOLD = 0.60
"""If sum of top-2 model sizes > 60% of available VRAM/RAM → sequential needed."""

UNIFIED_MEMORY_MAX_CONCURRENT_MODELS = 2
"""On unified memory, more than N distinct configured models → flag risk for concurrent."""


# ============================================================================
# Capability Assessment Signal Descriptors (CTO_PLAN.md §4.1)
# ============================================================================

class DetectionSignal:
    """Named descriptor for one auto-detection signal."""

    def __init__(self, name: str, source: str, threshold_desc: str):
        self.name = name
        self.source = source
        self.threshold_desc = threshold_desc


DETECTION_SIGNALS = [
    DetectionSignal(
        "total_memory",
        "/proc/meminfo or psutil",
        f"< {TOTAL_MEMORY_CONCURRENT_THRESHOLD_GB}GB → disqualify concurrent"
    ),
    DetectionSignal(
        "gpu_vram",
        "nvidia-smi (discrete GPU)",
        "If discrete GPU exists AND per-model size fits coherently → concurrent possible"
    ),
    DetectionSignal(
        "memory_type",
        "/dev/dri, lspci, or platform module",
        f"Unified memory + total RAM < {UNIFIED_MEMORY_CONCURRENT_THRESHOLD_GB}GB → favor sequential"
    ),
    DetectionSignal(
        "model_sizes",
        "ollama show --format json (file sizes)",
        f"If sum of top-2 model sizes > {MODEL_SIZE_VRAM_RATIO_THRESHOLD:.0%} of available GPU/RAM → sequential needed"
    ),
    DetectionSignal(
        "active_models_count",
        "/api/ps from Ollama",
        "If ≥ 2 large models already resident + any new load needed → sequential recommended"
    ),
    DetectionSignal(
        "distinct_agent_models",
        "agents_list.json (count distinct models)",
        f"> {UNIFIED_MEMORY_MAX_CONCURRENT_MODELS} distinct models on unified memory → flag risk"
    ),
]


# ============================================================================
# Selection Source Tags
# ============================================================================

SELECTION_SOURCE_AUTO = "auto"
SELECTION_SOURCE_USER_OVERRIDE = "user_override"
