"""
DS-EO Session Health — Configuration (§10, §23)

All thresholds configurable via YAML with conservative defaults.
No arbitrary hardcoded values in business logic.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


# Default conservative configuration values
DEFAULT_STALE_AFTER_SECONDS = 3600         # 1 hour (conservative — longer than idle threshold)
DEFAULT_OVERSIZED_CONTEXT_KB = 51200       # 50 MB
DEFAULT_MAX_COMPACTION_ATTEMPTS = 2
DEFAULT_ERROR_THRESHOLD = 3                # errors before ERRORING classification
DEFAULT_ORPHAN_INACTIVE_SECONDS = 7200     # 2 hours for orphan detection
DEFAULT_MONITORING_INTERVAL_SECONDS = 300  # 5 minute polling (None = monitoring disabled)
DEFAULT_OBSERVE_BY_DEFAULT = True          # dry-run default (§23)


@dataclass
class SessionHealthConfig:
    """Configuration for session health monitoring.

    All values have conservative defaults. Override via YAML config or direct
    construction. No arbitrary thresholds in business logic — everything here.
    """
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS
    oversized_context_kb: int = DEFAULT_OVERSIZED_CONTEXT_KB
    max_compaction_attempts: int = DEFAULT_MAX_COMPACTION_ATTEMPTS
    error_threshold: int = DEFAULT_ERROR_THRESHOLD
    orphan_inactive_seconds: int = DEFAULT_ORPHAN_INACTIVE_SECONDS
    monitoring_interval_seconds: Optional[int] = DEFAULT_MONITORING_INTERVAL_SECONDS
    observe_by_default: bool = DEFAULT_OBSERVE_BY_DEFAULT

    def is_monitoring_enabled(self) -> bool:
        """True when a non-None interval means periodic monitoring."""
        return self.monitoring_interval_seconds is not None

    def to_dict(self) -> dict:
        """Serialize to dict for YAML export / manifest integration."""
        return {
            "stale_after_seconds": self.stale_after_seconds,
            "oversized_context_kb": self.oversized_context_kb,
            "max_compaction_attempts": self.max_compaction_attempts,
            "error_threshold": self.error_threshold,
            "orphan_inactive_seconds": self.orphan_inactive_seconds,
            "monitoring_interval_seconds": self.monitoring_interval_seconds,
            "observe_by_default": self.observe_by_default,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionHealthConfig":
        """Deserialize from dict (e.g., YAML parsed). Missing keys use defaults."""
        return cls(
            stale_after_seconds=data.get("stale_after_seconds", DEFAULT_STALE_AFTER_SECONDS),
            oversized_context_kb=data.get("oversized_context_kb", DEFAULT_OVERSIZED_CONTEXT_KB),
            max_compaction_attempts=data.get("max_compaction_attempts", DEFAULT_MAX_COMPACTION_ATTEMPTS),
            error_threshold=data.get("error_threshold", DEFAULT_ERROR_THRESHOLD),
            orphan_inactive_seconds=data.get("orphan_inactive_seconds", DEFAULT_ORPHAN_INACTIVE_SECONDS),
            monitoring_interval_seconds=data.get("monitoring_interval_seconds", DEFAULT_MONITORING_INTERVAL_SECONDS),
            observe_by_default=data.get("observe_by_default", DEFAULT_OBSERVE_BY_DEFAULT),
        )

    @classmethod
    def from_yaml_path(cls, path: str) -> "SessionHealthConfig":
        """Load configuration from a YAML file. Falls back to defaults on error."""
        try:
            import yaml
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            # Support nested under 'session_health' key or top-level
            sh_data = data.get("session_health", data)
            return cls.from_dict(sh_data)
        except (ImportError, FileNotFoundError, ValueError):
            # YAML not installed or file missing — use defaults
            return cls()


def get_default_config() -> SessionHealthConfig:
    """Return the standard default configuration."""
    return SessionHealthConfig()
