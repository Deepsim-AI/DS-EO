"""Model Registry — Runtime-agnostic model resolution.

Replaces hardcoded ollama/* model references with a registry that
can resolve models for any target runtime (DSH, OpenClaw, etc.).

Usage:
    from ds_eo_dsh.adapter.model_registry import get_registry

    registry = get_registry()
    default_model = registry.default_model_for_role("cto")        # e.g., "ollama/qwen3.6:35b"
    resolved = registry.resolve("ollama/qwen3.6:35b", runtime="dsh")  # "dsh://model/qwen3.6:35b"

Covers Dependency A5: replaces hardcoded ollama/* model references
with runtime-agnostic resolution via ds_eo_manifest.yaml config.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional


# Default role → manifest mapping keys (from ds_eo_manifest.yaml)
_ROLE_TO_MANIFEST_KEY = {
    "cto": "default_model_cto",
    "implementer": "default_model_implementer",
    "reviewer": "default_model_reviewer",
    "pm": "default_model_pm",
}


# Fallback defaults when manifest is unavailable
_FALLBACK_MODELS = {
    "cto": "ollama/qwen3.6:35b",
    "implementer": "ollama/qwen3.8:27b",
    "reviewer": "ollama/laguna-xs-2.1:q4_K_M",
    "pm": "ollama/ornith:35b",
}


class ModelRegistry:
    """Runtime-agnostic model registry.

    Reads default models from ds_eo_manifest.yaml and provides
    resolution between runtime-specific model URIs (ollama/qwen3.6:35b)
    and target runtime URIs (dsh://model/..., etc.).
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize registry.

        Args:
            config_path: Path to ds_eo_manifest.yaml. Defaults to finding
                it relative to the caller's package location or CWD.
        """
        self._config_path = config_path or self._find_manifest()
        self._cache: dict[str, str] = {}

    def _find_manifest(self) -> Path:
        """Locate ds_eo_manifest.yaml relative to this package."""
        pkg_dir = Path(__file__).resolve().parent.parent  # ds_eo_dsh/
        cwd_manifest = Path.cwd() / "ds_eo_manifest.yaml"
        if cwd_manifest.exists():
            return cwd_manifest
        pkg_manifest = pkg_dir.parent / "ds_eo_manifest.yaml"
        if pkg_manifest.exists():
            return pkg_manifest
        raise FileNotFoundError(
            "ds_eo_manifest.yaml not found. Set config_path or place manifest in project root."
        )

    def load_from_yaml(self, path: Optional[Path] = None) -> dict[str, str]:
        """Load model defaults from ds_eo_manifest.yaml.

        Args:
            path: Path to manifest. Defaults to _config_path.

        Returns:
            Dict mapping role names to model URIs.
        """
        target = path or self._config_path
        try:
            import yaml  # lazy import — only when needed
        except ImportError:
            # PyYAML not installed; return empty dict so caller falls back to defaults
            return {}

        with open(target) as f:
            config = yaml.safe_load(f) or {}
        models = {}
        for role, key in _ROLE_TO_MANIFEST_KEY.items():
            model_val = config.get(key, {})
            if isinstance(model_val, dict):
                models[role] = model_val.get("default_model", "")
            elif isinstance(model_val, str):
                models[role] = model_val
        return models

    def default_model_for_role(self, role: str) -> str:
        """Get the default model URI for a given role.

        Args:
            role: Agent role name (cto, implementer, reviewer, pm)

        Returns:
            Model URI string from manifest or fallback.
        """
        # Unknown role -> None (does not raise). Callers such as
        # session_spawn.spawn_agent() treat None as "no model available"
        # and fail gracefully with a descriptive error.
        if role not in _ROLE_TO_MANIFEST_KEY:
            return None

        key = _ROLE_TO_MANIFEST_KEY[role]

        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Try manifest first
        try:
            models = self.load_from_yaml()
            value = models.get(key, "")
        except (FileNotFoundError, Exception):
            value = ""

        # Fallback to hardcoded defaults if manifest unavailable
        if not value:
            value = _FALLBACK_MODELS[role]

        self._cache[key] = value
        return value

    def resolve(self, model_uri: str, runtime: str = "openclaw") -> str:
        """Resolve a model URI from source runtime to target runtime.

        This is the pluggable mapping layer between runtimes.

        Args:
            model_uri: Source model URI (e.g., "ollama/qwen3.6:35b")
            runtime: Target runtime identifier ("dsh", "openclaw", etc.)

        Returns:
            Resolved model URI for target runtime.
        """
        if runtime == "dsh":
            # Strip any existing provider prefix, then add dsh://model/
            short_name = re.sub(r'^[a-z]+/', '', model_uri)
            return f"dsh://model/{short_name}"
        elif runtime == "openclaw":
            return model_uri  # No-op for legacy adapter compatibility
        else:
            return model_uri  # Passthrough for unknown runtimes


# Singleton instance — shared across all consumers
_model_registry: Optional[ModelRegistry] = None


def get_registry() -> ModelRegistry:
    """Get or create the singleton ModelRegistry instance."""
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
    return _model_registry


# Legacy default map — kept for backward compatibility with any code that
# directly references DEFAULT_MODEL_MAP. New consumers should use get_registry().
_LEGACY_DEFAULT_MODEL_MAP = {
    "implementer": "ollama/qwen3.6:27b",
    "reviewer": "ollama/laguna-xs-2.1:q4_K_M",
    "cto": "ollama/qwen3.6:35b",
    "pm": "ollama/gpt-oss:20b",
}


def legacy_default_model(role: str) -> str:
    """Legacy fallback — for backward compatibility only. Prefer get_registry()."""
    return _LEGACY_DEFAULT_MODEL_MAP.get(role, "")
