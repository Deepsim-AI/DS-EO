"""
Execution Strategy — CapabilityAssessor (Auto-Detection).

Phase A deliverable 5 of TASK_DS_EO_043.
Source of truth: CTO_PLAN.md §4.1.

Pure detection logic — no lifecycle management. Evaluates hardware signals
and returns a CapabilityReport recommending the most appropriate strategy.
"""

import json
import logging
import os
import subprocess
from typing import Optional

from .constants import (
    Strategy,
    DETECTION_SIGNALS,
    TOTAL_MEMORY_CONCURRENT_THRESHOLD_GB,
    UNIFIED_MEMORY_CONCURRENT_THRESHOLD_GB,
    MODEL_SIZE_VRAM_RATIO_THRESHOLD,
    UNIFIED_MEMORY_MAX_CONCURRENT_MODELS,
)
from .strategy_base import CapabilityReport

logger = logging.getLogger(__name__)


class CapabilityAssessor:
    """
    Auto-detect hardware capabilities and recommend an execution strategy.
    
    Evaluates 6 signals from CTO_PLAN.md §4.1 and applies the decision matrix
    to select between concurrent, sequential, or shared_model strategies.
    """

    @classmethod
    def assess(cls, workspace_root: str = None) -> CapabilityReport:
        """
        Run full capability assessment and return recommendation.
        
        Args:
            workspace_root: Path to DS-EO workspace (for registry lookup).
            
        Returns:
            CapabilityReport with recommended strategy and raw signal values.
        """
        signals = {}
        
        # Signal 1: Total system memory
        signals["total_memory_gb"] = cls.detect_total_memory()
        
        # Signal 2: GPU VRAM (discrete)
        signals["gpu_vram_gb"] = cls.detect_gpu_vram()
        
        # Signal 3: Memory type
        signals["memory_type"] = cls.detect_memory_type()
        
        # Signal 4: Configured model sizes
        signals["model_sizes_gb"] = cls.get_configured_model_sizes(workspace_root)
        
        # Signal 5: Active loaded models count
        signals["active_loaded_models"] = cls.count_active_loaded_models()
        
        # Signal 6: Distinct agent models count
        signals["distinct_agent_models"] = cls.count_distinct_agent_models(workspace_root)

        # Apply decision matrix from CTO_PLAN.md §4.1
        strategy, confidence, reason = cls._apply_decision_matrix(signals)

        return CapabilityReport(
            strategy=strategy.value if isinstance(strategy, Strategy) else strategy,
            confidence=confidence,
            signals=signals,
            reason=reason,
        )

    # ========================================================================
    # Detection Methods (one per signal)
    # ========================================================================

    @staticmethod
    def detect_total_memory() -> float:
        """Read total system memory in GB from /proc/meminfo or fallback."""
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        # Value is in kB, convert to GB
                        kb = int(line.split()[1])
                        return round(kb / (1024 * 1024), 2)
        except Exception as e:
            logger.warning(f"Failed to read /proc/meminfo: {e}")

        # Fallback: try psutil if available
        try:
            import psutil
            total_bytes = psutil.virtual_memory().total
            return round(total_bytes / (1024 ** 3), 2)
        except ImportError:
            logger.warning("psutil not available; returning default estimate")
            return 64.0  # conservative default

    @staticmethod
    def detect_gpu_vram() -> Optional[float]:
        """Detect discrete GPU VRAM via nvidia-smi. Returns None if no discrete GPU."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return None
            
            lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            total_gb = sum(float(l) / 1024 for l in lines)  # convert MB → GB
            return round(total_gb, 2) if total_gb > 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            return None

    @staticmethod
    def detect_memory_type() -> str:
        """
        Detect whether system uses unified or discrete memory.
        
        Returns "unified" for Tegra/Apple Silicon, "discrete" if nvidia GPU found,
        "unknown" otherwise.
        """
        # Check for NVIDIA discrete GPU
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return "discrete"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check for Tegra / ARM SoC (unified memory)
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
            if "tegra" in cpuinfo.lower():
                return "unified"
        except Exception:
            pass

        # Check for Apple Silicon (unlikely on Linux but be thorough)
        try:
            platform_name = subprocess.run(
                ["uname", "-m"], capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            if "arm64" in platform_name or "aarch64" in platform_name:
                # Could be Tegra or other ARM SoC with unified memory
                return "unified"
        except Exception:
            pass

        return "unknown"

    @staticmethod
    def get_configured_model_sizes(workspace_root: str = None) -> dict:
        """
        Resolve agent models via registry, then get file sizes via ollama list.
        
        Uses `ollama list` output (which returns human-readable sizes like "23 GB")
        rather than `ollama show --format json` which is not supported in all ollama versions.
        
        Returns dict of {model_name: size_gb}.
        """
        model_names = CapabilityAssessor._get_agent_model_names(workspace_root)
        if not model_names:
            return {}

        sizes = {}
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                logger.warning("ollama list failed")
                return {m: 20.0 for m in model_names}

            # Parse ollama list output: NAME ID SIZE MODIFIED
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # skip header
                parts = line.split()
                if len(parts) >= 3:
                    listed_model = parts[0]
                    size_str = parts[2]
                    gb = CapabilityAssessor._parse_size_gb(size_str)
                    if gb > 0:
                        sizes[listed_model] = round(gb, 2)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Could not list ollama models: {e}")

        # Map registry names (ollama/model:name) to listed names and fill gaps with estimates
        for model in model_names:
            short_name = model.replace("ollama/", "")
            if short_name in sizes:
                sizes[model] = sizes[short_name]  # use detected size
            elif model in sizes:
                pass  # already has it
            else:
                sizes[model] = 20.0  # fallback estimate

        return sizes

    @staticmethod
    def count_active_loaded_models() -> int:
        """Count currently loaded models via Ollama /api/ps."""
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/ps")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            
            # Count models that have active sessions (not just loaded idle)
            count = 0
            for model_info in data.get("models", []):
                if model_info.get("size_vram", 0) > 0 or model_info.get("expires_at"):
                    count += 1
            return count
        except Exception as e:
            logger.debug(f"Could not query /api/ps: {e}")
            return 0

    @staticmethod
    def count_distinct_agent_models(workspace_root: str = None) -> int:
        """Count distinct model names across all agents in registry."""
        model_names = CapabilityAssessor._get_agent_model_names(workspace_root)
        return len(set(model_names)) if model_names else 0

    # ========================================================================
    # Decision Matrix (CTO_PLAN.md §4.1)
    # ========================================================================

    @staticmethod
    def _apply_decision_matrix(signals: dict):
        """
        Apply the auto-selection decision matrix.
        
        Returns: (Strategy, confidence, reason)
        """
        total_mem = signals.get("total_memory_gb", 0)
        vram = signals.get("gpu_vram_gb")
        mem_type = signals.get("memory_type", "unknown")
        model_sizes = signals.get("model_sizes_gb", {})
        active_models = signals.get("active_loaded_models", 0)
        distinct_models = signals.get("distinct_agent_models", 1)

        # Convert model sizes to GB list for ratio calculation
        size_values = sorted(model_sizes.values(), reverse=True) if model_sizes else []

        # Decision: discrete GPU exists → concurrent is safe (identity wrap of existing behavior)
        if vram is not None and vram > 0:
            if len(size_values) >= 2:
                top2_ratio = (size_values[0] + size_values[1]) / vram
                confidence = 0.80
                reason_suffix = f"; top-2 models use {top2_ratio:.0%} of VRAM" if top2_ratio <= MODEL_SIZE_VRAM_RATIO_THRESHOLD else f"; top-2 models use {top2_ratio:.0%} of VRAM (models may swap to CPU)"
                return (
                    Strategy.CONCURRENT,
                    confidence,
                    f"Discrete GPU with {vram}GB VRAM — concurrent feasible ({reason_suffix})",
                )
            # Single large model on discrete GPU
            if len(size_values) == 1:
                return (
                    Strategy.CONCURRENT,
                    0.80,
                    f"Discrete GPU with {vram}GB VRAM; single model fits — concurrent feasible",
                )

        # Decision: unified memory path
        if mem_type == "unified":
            if total_mem >= UNIFIED_MEMORY_CONCURRENT_THRESHOLD_GB:
                # 64GB+ on unified can sometimes handle two models
                if distinct_models <= UNIFIED_MEMORY_MAX_CONCURRENT_MODELS:
                    return (
                        Strategy.CONCURRENT,
                        0.50,
                        f"Unified memory {total_mem}GB with {distinct_models} model(s) — concurrent borderline but possible",
                    )
                else:
                    return (
                        Strategy.SEQUENTIAL,
                        0.90,
                        f"Unified memory {total_mem}GB but {distinct_models} models configured — sequential safer to avoid bandwidth saturation",
                    )
            else:
                # < 64GB unified → sequential
                top2_total = sum(size_values[:2]) if len(size_values) >= 2 else (size_values[0] if size_values else 0)
                return (
                    Strategy.SEQUENTIAL,
                    0.95,
                    f"Unified memory {total_mem}GB with top-2 models totaling ~{top2_total:.1f}GB — sequential required to avoid OOM/bandwidth saturation",
                )

        # Decision: unknown memory type → shared_model as fallback
        if distinct_models > 1 and model_sizes:
            # If multiple agents share models, shared_model is a safe default
            return (
                Strategy.SHARED_MODEL,
                0.70,
                f"Unknown memory topology; {distinct_models} agent models configured — shared_model avoids unnecessary loading",
            )

        # Default fallback: sequential (safest for constrained systems)
        return (
            Strategy.SEQUENTIAL,
            0.60,
            "Unable to determine hardware capability; defaulting to sequential for safety",
        )

    # ========================================================================
    # Helpers
    # ========================================================================

    @staticmethod
    def _parse_size_gb(size_str: str) -> float:
        """Parse human-readable size string (e.g., '23 GB', '274 MB') to GB."""
        if not size_str:
            return 0.0
        parts = size_str.upper().split()
        try:
            value = float(parts[0])
            unit = parts[1] if len(parts) > 1 else ''
            if unit == 'GB':
                return value
            elif unit == 'MB':
                return value / 1024.0
            elif unit == 'KB':
                return value / (1024 * 1024)
            else:
                # Assume GB for bare numbers
                return value
        except (ValueError, IndexError):
            return 0.0

    @staticmethod
    def _get_agent_model_names(workspace_root: str = None) -> list:
        """Extract unique model names from agents_list.json."""
        if workspace_root is None:
            workspace_root = os.path.join(os.getcwd())

        registry_path = os.path.join(workspace_root, "agents_list.json")
        try:
            with open(registry_path, "r") as f:
                agents = json.load(f)
            
            models = []
            for agent in agents:
                model = agent.get("model", "")
                if model:
                    models.append(model)
            return list(set(models))  # deduplicate
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            logger.warning(f"Could not read {registry_path} for model names")
            return []
